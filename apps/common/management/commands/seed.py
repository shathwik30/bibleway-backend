"""
Management command to seed the database with minimal test data.

Usage:
    python manage.py seed              # drop all + seed everything
    python manage.py seed --only accounts social  # seed specific apps
"""

import uuid
from datetime import date, timedelta
from decimal import Decimal

from django.contrib.contenttypes.models import ContentType
from django.core.management.base import BaseCommand
from django.db import connection, transaction
from django.utils import timezone


class Command(BaseCommand):
    help = "Drop all app data and seed minimal test data."

    def add_arguments(self, parser):
        parser.add_argument(
            "--only",
            nargs="+",
            choices=[
                "accounts", "bible", "social", "shop",
                "notifications", "analytics", "verse_of_day", "admin_panel",
            ],
            help="Seed only specific apps.",
        )

    def handle(self, *args, **options):
        self.stdout.write(self.style.NOTICE("Starting database seed..."))

        apps_to_seed = options["only"] or [
            "accounts", "bible", "social", "shop",
            "notifications", "analytics", "verse_of_day", "admin_panel",
        ]

        # Always flush first
        self._flush()

        with transaction.atomic():
            users = []
            if "accounts" in apps_to_seed:
                users = self._seed_accounts()

            if not users:
                from apps.accounts.models import User
                users = list(User.objects.filter(is_active=True)[:5])
                if not users:
                    self.stdout.write(self.style.ERROR("No users. Include 'accounts'."))
                    return

            pages = []
            if "bible" in apps_to_seed:
                pages = self._seed_bible(users)

            posts, prayers = [], []
            if "social" in apps_to_seed:
                posts, prayers = self._seed_social(users)

            if "shop" in apps_to_seed:
                self._seed_shop(users)

            if "notifications" in apps_to_seed:
                self._seed_notifications(users)

            if "analytics" in apps_to_seed:
                self._seed_analytics(users, posts, prayers)

            if "verse_of_day" in apps_to_seed:
                self._seed_verse_of_day()

            if "admin_panel" in apps_to_seed:
                self._seed_admin_panel(users)

        self.stdout.write(self.style.SUCCESS("Database seeded successfully!"))

    def _flush(self):
        """TRUNCATE all app tables in one shot."""
        app_tables = [
            # analytics
            "analytics_boostanalyticsnapshot", "analytics_postboost", "analytics_postview",
            # notifications
            "notifications_notification", "notifications_devicepushtoken",
            # social
            "social_reply", "social_report", "social_reaction", "social_comment",
            "social_postmedia", "social_post", "social_prayermedia", "social_prayer",
            # shop
            "shop_download", "shop_purchase", "shop_product",
            # bible
            "bible_segregatedpagecomment", "bible_segregatedpagelike",
            "bible_translatedpagecache", "bible_note", "bible_highlight",
            "bible_bookmark", "bible_segregatedpage", "bible_segregatedchapter",
            "bible_segregatedsection",
            # verse_of_day
            "verse_of_day_verseofday", "verse_of_day_versefallbackpool",
            # admin_panel
            "admin_panel_adminlog", "admin_panel_adminrole", "admin_panel_boosttier",
            # accounts (last — everything else FKs to it)
            "accounts_otptoken", "accounts_blockrelationship",
            "accounts_followrelationship", "accounts_user",
            # token blacklist
            "token_blacklist_blacklistedtoken", "token_blacklist_outstandingtoken",
        ]
        table_list = ", ".join(f'"{t}"' for t in app_tables)
        with connection.cursor() as cursor:
            cursor.execute(f"TRUNCATE {table_list} CASCADE")
        self.stdout.write(f"  Truncated {len(app_tables)} tables")

    # ── Accounts (5 users) ────────────────────────────────────────

    def _seed_accounts(self):
        from apps.accounts.models import BlockRelationship, FollowRelationship, User

        self.stdout.write("Seeding accounts...")

        user_data = [
            {"email": "testuser@bibleway.app", "full_name": "Test User",
             "dob": date(1995, 6, 15), "gender": "male", "country": "United States",
             "lang": "en", "bio": "A test account for development and QA.",
             "visibility": "public"},
            {"email": "jane@bibleway.app", "full_name": "Jane Smith",
             "dob": date(1990, 3, 20), "gender": "female", "country": "Nigeria",
             "lang": "en", "bio": "Walking by faith, not by sight.",
             "visibility": "public"},
            {"email": "carlos@bibleway.app", "full_name": "Carlos Rivera",
             "dob": date(1988, 11, 5), "gender": "male", "country": "Brazil",
             "lang": "es", "bio": "Youth pastor. Bible nerd.",
             "visibility": "public"},
            {"email": "grace@bibleway.app", "full_name": "Grace Kim",
             "dob": date(2000, 7, 12), "gender": "female", "country": "South Korea",
             "lang": "ko", "bio": "New believer hungry to learn.",
             "visibility": "private"},
            {"email": "admin@bibleway.app", "full_name": "Admin User",
             "dob": date(1985, 1, 1), "gender": "male", "country": "United States",
             "lang": "en", "bio": "Platform administrator.",
             "visibility": "public"},
        ]

        users = []
        for d in user_data:
            u = User(
                email=d["email"], full_name=d["full_name"],
                date_of_birth=d["dob"], gender=d["gender"],
                country=d["country"], preferred_language=d["lang"],
                bio=d["bio"], is_email_verified=True,
                account_visibility=d["visibility"],
            )
            u.set_password("testpass123")
            u.save()
            users.append(u)

        self.stdout.write(f"  {len(users)} users created (all pw: testpass123)")

        # Follows: user0↔user1, user0→user2, user1→user2, user2→user3(pending)
        follows = [
            (users[0], users[1], "accepted"),
            (users[1], users[0], "accepted"),
            (users[0], users[2], "accepted"),
            (users[1], users[2], "accepted"),
            (users[2], users[3], "pending"),  # private account
            (users[3], users[0], "accepted"),
            (users[2], users[0], "accepted"),
        ]
        FollowRelationship.objects.bulk_create([
            FollowRelationship(follower=f, following=t, status=s)
            for f, t, s in follows
        ])
        self.stdout.write(f"  {len(follows)} follow relationships created")

        # 1 block: user0 blocks user4's admin account (edge case test)
        BlockRelationship.objects.create(blocker=users[0], blocked=users[4])
        self.stdout.write("  1 block relationship created")

        return users

    # ── Bible (1 section → 2 chapters → 2 pages each) ────────────

    def _seed_bible(self, users):
        from apps.bible.models import (
            Bookmark, Highlight, Note, SegregatedChapter, SegregatedPage,
            SegregatedPageComment, SegregatedPageLike, SegregatedSection,
            TranslatedPageCache,
        )

        self.stdout.write("Seeding bible...")

        # 2 sections
        sec_kids = SegregatedSection.objects.create(
            title="Little Lambs", age_min=5, age_max=12, order=0,
        )
        sec_adults = SegregatedSection.objects.create(
            title="Adults", age_min=13, age_max=99, order=1,
        )

        # 2 chapters per section
        ch1 = SegregatedChapter.objects.create(
            section=sec_kids, title="In the Beginning", order=0,
        )
        ch2 = SegregatedChapter.objects.create(
            section=sec_kids, title="Noah and the Ark", order=1,
        )
        ch3 = SegregatedChapter.objects.create(
            section=sec_adults, title="The Sermon on the Mount", order=0,
        )
        ch4 = SegregatedChapter.objects.create(
            section=sec_adults, title="Paul's Letters", order=1,
        )

        # 2 pages per chapter
        pages = []
        page_data = [
            (ch1, "Creation - Part 1", "# Creation\n\nIn the beginning God created the heavens and the earth.\n\n> *\"For God so loved the world...\"* — John 3:16"),
            (ch1, "Creation - Part 2", "# Creation Continued\n\nGod saw all that he had made, and it was very good.\n\n> *\"The Lord is my shepherd\"* — Psalm 23:1"),
            (ch2, "The Flood - Part 1", "# Noah's Ark\n\nNoah found favor in the eyes of the Lord.\n\n> *\"Trust in the Lord with all your heart\"* — Proverbs 3:5-6"),
            (ch2, "The Flood - Part 2", "# The Rainbow\n\nGod set a rainbow in the clouds as a sign of His covenant.\n\n> *\"I can do all this through him\"* — Philippians 4:13"),
            (ch3, "Beatitudes", "# The Beatitudes\n\nBlessed are the poor in spirit, for theirs is the kingdom of heaven.\n\n> *\"Come to me, all you who are weary\"* — Matthew 11:28"),
            (ch3, "Salt and Light", "# Salt and Light\n\nYou are the salt of the earth. You are the light of the world.\n\n> *\"Your word is a lamp for my feet\"* — Psalm 119:105"),
            (ch4, "Romans Overview", "# Romans\n\nFor all have sinned and fall short of the glory of God.\n\n> *\"And we know that in all things God works for the good\"* — Romans 8:28"),
            (ch4, "Philippians Overview", "# Philippians\n\nRejoice in the Lord always. I will say it again: Rejoice!\n\n> *\"I can do all this through him who gives me strength\"* — Philippians 4:13"),
        ]
        for i, (ch, title, content) in enumerate(page_data):
            p = SegregatedPage.objects.create(
                chapter=ch, title=title, content=content, order=i % 2,
                youtube_url="https://www.youtube.com/watch?v=dQw4w9WgXcQ" if i == 0 else "",
            )
            pages.append(p)

        self.stdout.write(f"  2 sections, 4 chapters, {len(pages)} pages")

        # 1 translation cache
        TranslatedPageCache.objects.create(
            page=pages[0], language_code="es",
            translated_content="[ES] # Creación\n\nEn el principio Dios creó los cielos y la tierra.",
        )
        self.stdout.write("  1 translation cache")

        page_ct = ContentType.objects.get_for_model(SegregatedPage)

        # 2 bookmarks (1 API Bible, 1 segregated)
        Bookmark.objects.create(
            user=users[0], bookmark_type="api_bible",
            verse_reference="JHN.3.16",
        )
        Bookmark.objects.create(
            user=users[0], bookmark_type="segregated",
            content_type=page_ct, object_id=pages[0].id,
        )
        self.stdout.write("  2 bookmarks")

        # 2 highlights
        Highlight.objects.create(
            user=users[0], highlight_type="api_bible",
            verse_reference="PSA.23.1", color="yellow",
        )
        Highlight.objects.create(
            user=users[1], highlight_type="segregated",
            content_type=page_ct, object_id=pages[4].id,
            color="green", selection_start=0, selection_end=50,
        )
        self.stdout.write("  2 highlights")

        # 2 notes
        Note.objects.create(
            user=users[0], note_type="api_bible",
            verse_reference="ROM.8.28", text="This verse gives me so much comfort.",
        )
        Note.objects.create(
            user=users[1], note_type="segregated",
            content_type=page_ct, object_id=pages[5].id,
            text="Great lesson on being salt and light.",
        )
        self.stdout.write("  2 notes")

        # 2 page comments + 2 page likes
        SegregatedPageComment.objects.create(
            user=users[1], page=pages[0], content="Beautiful story of creation!",
        )
        SegregatedPageComment.objects.create(
            user=users[2], page=pages[4], content="The beatitudes are life-changing.",
        )
        SegregatedPageLike.objects.create(user=users[0], page=pages[0])
        SegregatedPageLike.objects.create(user=users[1], page=pages[4])
        self.stdout.write("  2 page comments, 2 page likes")

        return pages

    # ── Social (3 posts, 2 prayers, reactions, comments, replies, report) ──

    def _seed_social(self, users):
        from apps.social.models import Comment, Post, Prayer, Reaction, Reply, Report

        self.stdout.write("Seeding social...")

        post_ct = ContentType.objects.get_for_model(Post)
        prayer_ct = ContentType.objects.get_for_model(Prayer)

        # 3 posts (1 boosted)
        p1 = Post.objects.create(
            author=users[0],
            text_content="Just finished my morning devotion. What a beautiful day to praise the Lord!",
        )
        p2 = Post.objects.create(
            author=users[1],
            text_content="God's grace is sufficient. No matter what you're going through, He is with you.",
        )
        p3 = Post.objects.create(
            author=users[2],
            text_content="Started a new Bible reading plan. Who wants to join me?",
            is_boosted=True,
        )
        posts = [p1, p2, p3]
        self.stdout.write(f"  {len(posts)} posts (1 boosted)")

        # 2 prayers
        pr1 = Prayer.objects.create(
            author=users[1], title="Healing for my mother",
            description="Please pray for my mother who is battling cancer.",
        )
        pr2 = Prayer.objects.create(
            author=users[3], title="Job search guidance",
            description="I've been looking for work for 3 months. Praying for God to open the right door.",
        )
        prayers = [pr1, pr2]
        self.stdout.write(f"  {len(prayers)} prayers")

        # Reactions (a few per post/prayer)
        reactions = [
            (users[1], post_ct, p1.id, "heart"),
            (users[2], post_ct, p1.id, "amen"),
            (users[0], post_ct, p2.id, "praying_hands"),
            (users[3], post_ct, p3.id, "fire"),
            (users[0], prayer_ct, pr1.id, "praying_hands"),
            (users[2], prayer_ct, pr1.id, "heart"),
            (users[0], prayer_ct, pr2.id, "praying_hands"),
            (users[1], prayer_ct, pr2.id, "praying_hands"),
        ]
        Reaction.objects.bulk_create([
            Reaction(user=u, content_type=ct, object_id=oid, emoji_type=e)
            for u, ct, oid, e in reactions
        ])
        self.stdout.write(f"  {len(reactions)} reactions")

        # Comments
        c1 = Comment.objects.create(
            user=users[1], content_type=post_ct, object_id=p1.id,
            text="Amen! Praying for you!",
        )
        c2 = Comment.objects.create(
            user=users[2], content_type=post_ct, object_id=p2.id,
            text="This is so encouraging. Thank you for sharing!",
        )
        c3 = Comment.objects.create(
            user=users[0], content_type=prayer_ct, object_id=pr1.id,
            text="Standing in agreement with you in prayer.",
        )
        self.stdout.write("  3 comments")

        # Replies
        Reply.objects.create(user=users[0], comment=c1, text="Thank you so much!")
        Reply.objects.create(user=users[1], comment=c3, text="God is faithful!")
        self.stdout.write("  2 replies")

        # 1 report
        Report.objects.create(
            reporter=users[3], content_type=post_ct, object_id=p3.id,
            reason="spam", description="Looks like promotional content.",
        )
        self.stdout.write("  1 report")

        return posts, prayers

    # ── Shop (3 products, 1 purchase, 1 free download) ────────────

    def _seed_shop(self, users):
        from apps.shop.models import Download, Product, Purchase

        self.stdout.write("Seeding shop...")

        prod_paid1 = Product.objects.create(
            title="Daily Devotional Journal",
            description="A 365-day guided journal for deepening your walk with God.",
            price_tier="com.bibleway.shop.devotionals",
            is_free=False, category="devotionals", download_count=42,
            apple_product_id="com.bibleway.ios.daily_devotional",
            google_product_id="com.bibleway.android.daily_devotional",
        )
        prod_paid2 = Product.objects.create(
            title="Bible Study Workbook: Romans",
            description="In-depth study guide for the book of Romans.",
            price_tier="com.bibleway.shop.study_guides",
            is_free=False, category="study_guides", download_count=18,
            apple_product_id="com.bibleway.ios.romans_study",
            google_product_id="com.bibleway.android.romans_study",
        )
        prod_free = Product.objects.create(
            title="Prayer Guide for Beginners",
            description="A comprehensive guide to developing a powerful prayer life.",
            price_tier="", is_free=True, category="prayer", download_count=120,
        )
        self.stdout.write("  3 products (2 paid, 1 free)")

        # 1 purchase + download
        txn_id = f"txn_{uuid.uuid4().hex[:16]}"
        purchase = Purchase.objects.create(
            user=users[0], product=prod_paid1, platform="ios",
            receipt_data=f'{{"transaction_id": "{txn_id}"}}',
            transaction_id=txn_id, is_validated=True,
        )
        Download.objects.create(user=users[0], product=prod_paid1, purchase=purchase)
        self.stdout.write("  1 purchase + download")

        # 2 free downloads
        Download.objects.create(user=users[0], product=prod_free, purchase=None)
        Download.objects.create(user=users[1], product=prod_free, purchase=None)
        self.stdout.write("  2 free downloads")

    # ── Notifications (5 notifications, 2 device tokens) ──────────

    def _seed_notifications(self, users):
        from apps.notifications.models import DevicePushToken, Notification

        self.stdout.write("Seeding notifications...")

        Notification.objects.bulk_create([
            Notification(
                recipient=users[0], sender=users[1],
                notification_type="follow", title="New Follower",
                body=f"{users[1].full_name} started following you.",
                data={"screen": "profile", "id": str(users[1].id)},
            ),
            Notification(
                recipient=users[0], sender=users[2],
                notification_type="reaction", title="New Reaction",
                body=f"{users[2].full_name} reacted to your post.",
                data={"screen": "post_detail", "id": str(uuid.uuid4())},
            ),
            Notification(
                recipient=users[1], sender=users[0],
                notification_type="comment", title="New Comment",
                body=f"{users[0].full_name} commented on your prayer.",
                data={"screen": "prayer_detail", "id": str(uuid.uuid4())},
            ),
            Notification(
                recipient=users[0], sender=None,
                notification_type="system_broadcast", title="BibleWay Update",
                body="Check out our new Bible reading plans!",
                data={},
            ),
            Notification(
                recipient=users[3], sender=users[1],
                notification_type="prayer_comment", title="Prayer Support",
                body=f"{users[1].full_name} is praying for you.",
                data={"screen": "prayer_detail", "id": str(uuid.uuid4())},
                is_read=True,
            ),
        ])
        self.stdout.write("  5 notifications")

        DevicePushToken.objects.create(
            user=users[0], token=f"fcm_{uuid.uuid4().hex}", platform="ios",
        )
        DevicePushToken.objects.create(
            user=users[1], token=f"fcm_{uuid.uuid4().hex}", platform="android",
        )
        self.stdout.write("  2 device tokens")

    # ── Analytics (views + 1 boost with snapshot) ─────────────────

    def _seed_analytics(self, users, posts, prayers):
        from apps.analytics.models import BoostAnalyticSnapshot, PostBoost, PostView
        from apps.social.models import Post as PostModel, Prayer as PrayerModel

        self.stdout.write("Seeding analytics...")

        post_ct = ContentType.objects.get_for_model(PostModel)
        prayer_ct = ContentType.objects.get_for_model(PrayerModel)

        if not posts:
            posts = list(PostModel.objects.all()[:3])
        if not prayers:
            prayers = list(PrayerModel.objects.all()[:2])

        # A few views per post/prayer
        views = []
        for post in posts:
            for viewer in users[:3]:
                views.append(PostView(content_type=post_ct, object_id=post.id, viewer=viewer))
        for prayer in prayers:
            for viewer in users[:2]:
                views.append(PostView(content_type=prayer_ct, object_id=prayer.id, viewer=viewer))
        PostView.objects.bulk_create(views)
        self.stdout.write(f"  {len(views)} post/prayer views")

        # 1 boost on the boosted post
        boosted = [p for p in posts if p.is_boosted]
        if boosted:
            now = timezone.now()
            activated = now - timedelta(days=2)
            boost = PostBoost.objects.create(
                post=boosted[0], user=boosted[0].author,
                tier="com.bibleway.boost.3d",
                platform="ios",
                transaction_id=f"boost_txn_{uuid.uuid4().hex[:16]}",
                duration_days=3, is_active=True,
                activated_at=activated,
                expires_at=activated + timedelta(days=3),
            )
            # 2 daily snapshots
            for day in range(2):
                BoostAnalyticSnapshot.objects.create(
                    boost=boost,
                    snapshot_date=(activated + timedelta(days=day)).date(),
                    impressions=500 + day * 200,
                    reach=300 + day * 100,
                    engagement_rate=Decimal("4.50"),
                    link_clicks=25 + day * 10,
                    profile_visits=12 + day * 5,
                )
            self.stdout.write("  1 boost + 2 analytics snapshots")

    # ── Verse of the Day (3 scheduled + 3 fallback) ───────────────

    def _seed_verse_of_day(self):
        from apps.verse_of_day.models import VerseFallbackPool, VerseOfDay

        self.stdout.write("Seeding verse of the day...")

        today = date.today()
        verses = [
            ("John 3:16", "For God so loved the world that he gave his one and only Son, that whoever believes in him shall not perish but have eternal life."),
            ("Psalm 23:1", "The Lord is my shepherd, I lack nothing."),
            ("Philippians 4:13", "I can do all this through him who gives me strength."),
        ]

        for i, (ref, text) in enumerate(verses):
            VerseOfDay.objects.create(
                bible_reference=ref, verse_text=text,
                display_date=today + timedelta(days=i),
            )
            VerseFallbackPool.objects.create(
                bible_reference=ref, verse_text=text,
            )

        self.stdout.write("  3 scheduled verses + 3 fallback pool")

    # ── Admin Panel (1 admin role, 3 boost tiers, 1 log) ──────────

    def _seed_admin_panel(self, users):
        from apps.admin_panel.models import AdminLog, AdminRole, BoostTier

        self.stdout.write("Seeding admin panel...")

        # Make last user (admin@bibleway.app) a super admin
        admin_user = users[4] if len(users) > 4 else users[0]
        admin_user.is_staff = True
        admin_user.save(update_fields=["is_staff"])
        AdminRole.objects.create(user=admin_user, role="super_admin")
        self.stdout.write("  1 admin role (super_admin)")

        # Boost tiers
        BoostTier.objects.bulk_create([
            BoostTier(
                name="1-Day Boost",
                apple_product_id="com.bibleway.boost.1d.ios",
                google_product_id="com.bibleway.boost.1d.android",
                duration_days=1, display_price="$0.99",
            ),
            BoostTier(
                name="3-Day Boost",
                apple_product_id="com.bibleway.boost.3d.ios",
                google_product_id="com.bibleway.boost.3d.android",
                duration_days=3, display_price="$2.49",
            ),
            BoostTier(
                name="7-Day Boost",
                apple_product_id="com.bibleway.boost.7d.ios",
                google_product_id="com.bibleway.boost.7d.android",
                duration_days=7, display_price="$4.99",
            ),
        ])
        self.stdout.write("  3 boost tiers")

        AdminLog.objects.create(
            admin_user=admin_user, action="create",
            target_model="bible.SegregatedSection",
            target_id=str(uuid.uuid4()),
            detail="Created new Bible section",
            metadata={"seeded": True},
        )
        self.stdout.write("  1 admin log")
