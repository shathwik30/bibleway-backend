"""Seed the database with realistic test data.

Usage:
    python manage.py seed          # full seed
    python manage.py seed --flush  # flush DB first, then seed
"""

from __future__ import annotations

import datetime
import random
import uuid
from typing import Any

from django.contrib.contenttypes.models import ContentType
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

PASSWORD = "TestPass1!"

USERS_DATA: list[dict[str, Any]] = [
    {"full_name": "Sarah Johnson", "email": "sarah@bibleway.test", "gender": "female", "country": "US", "bio": "Passionate about spreading God's word. Youth group leader.", "date_of_birth": datetime.date(1995, 3, 12)},
    {"full_name": "David Kim", "email": "david@bibleway.test", "gender": "male", "country": "KR", "bio": "Seminary student. Love discussing theology.", "date_of_birth": datetime.date(1998, 7, 22)},
    {"full_name": "Maria Garcia", "email": "maria@bibleway.test", "gender": "female", "country": "MX", "bio": "Worship leader at my local church. Blessed.", "date_of_birth": datetime.date(1992, 11, 5)},
    {"full_name": "James Wilson", "email": "james@bibleway.test", "gender": "male", "country": "GB", "bio": "Bible teacher and podcast host.", "date_of_birth": datetime.date(1988, 1, 30)},
    {"full_name": "Priya Sharma", "email": "priya@bibleway.test", "gender": "female", "country": "IN", "bio": "Finding peace through scripture every day.", "date_of_birth": datetime.date(2001, 5, 18)},
    {"full_name": "Michael Brown", "email": "michael@bibleway.test", "gender": "male", "country": "US", "bio": "Pastor at Grace Community Church.", "date_of_birth": datetime.date(1985, 9, 8)},
    {"full_name": "Rachel Lee", "email": "rachel@bibleway.test", "gender": "female", "country": "SG", "bio": "Missionary kid turned youth pastor.", "date_of_birth": datetime.date(1997, 12, 3)},
    {"full_name": "Emmanuel Okafor", "email": "emmanuel@bibleway.test", "gender": "male", "country": "NG", "bio": "Choir director. Psalms are my love language.", "date_of_birth": datetime.date(1993, 4, 25)},
    {"full_name": "Anna Mueller", "email": "anna@bibleway.test", "gender": "female", "country": "DE", "bio": "Christian author and blogger.", "date_of_birth": datetime.date(1990, 6, 14)},
    {"full_name": "Joshua Martinez", "email": "joshua@bibleway.test", "gender": "male", "country": "US", "bio": "College ministry leader. Philippians 4:13.", "date_of_birth": datetime.date(2000, 8, 20)},
    {"full_name": "Grace Chen", "email": "grace@bibleway.test", "gender": "female", "country": "TW", "bio": "Sunday school teacher for 10 years.", "date_of_birth": datetime.date(1987, 2, 11)},
    {"full_name": "Daniel Abebe", "email": "daniel@bibleway.test", "gender": "male", "country": "ET", "bio": "Theology student. Love the Epistles.", "date_of_birth": datetime.date(1999, 10, 7)},
    {"full_name": "Sophie Williams", "email": "sophie@bibleway.test", "gender": "female", "country": "AU", "bio": "Newlywed, building a Christ-centered home.", "date_of_birth": datetime.date(1996, 7, 16)},
    {"full_name": "Carlos Rivera", "email": "carlos@bibleway.test", "gender": "male", "country": "CO", "bio": "Church planter in Bogota. Isaiah 6:8.", "date_of_birth": datetime.date(1991, 3, 28)},
    {"full_name": "Fatima Hassan", "email": "fatima@bibleway.test", "gender": "female", "country": "KE", "bio": "Community outreach coordinator.", "date_of_birth": datetime.date(1994, 12, 22)},
]

POST_TEXTS = [
    "Just finished reading through the book of Romans. Paul's letter to the Romans is so powerful! What are your favorite verses from this book?",
    "Morning devotional thought: 'Be still, and know that I am God.' - Psalm 46:10. Sometimes we need to pause and just listen.",
    "Our church youth group had an amazing retreat this weekend! 30 kids gave their lives to Christ. God is so good!",
    "Struggling with anxiety lately but clinging to Philippians 4:6-7. 'Do not be anxious about anything, but in everything by prayer...'",
    "Just led worship for the first time at our new church plant. Tears of joy! God's faithfulness is beyond measure.",
    "Reading Proverbs 3:5-6 this morning. Trust in the Lord with all your heart. Such a timely reminder.",
    "Had the most beautiful conversation with a stranger at the coffee shop about faith today. God opens doors when we least expect it.",
    "Bible study question: What does it mean to 'run the race with endurance' (Hebrews 12:1)? Share your thoughts!",
    "Grateful for this community! Being connected with fellow believers around the world is such a blessing.",
    "The sermon today on the Beatitudes really challenged me. What does it look like to be a peacemaker in 2026?",
    "Starting a 40-day prayer challenge. Who wants to join me? Let's hold each other accountable!",
    "Just discovered a beautiful verse: 'The steadfast love of the Lord never ceases' - Lamentations 3:22. How true!",
    "Our small group finished studying the book of James. Faith without works is dead — what a convicting message.",
    "Praising God for answered prayers today! He is faithful even when we doubt. Never stop praying, friends.",
    "Volunteered at the food bank today with our church family. Serving others is where we truly find Jesus.",
    "Does anyone have recommendations for good devotionals? Looking for something deep but accessible.",
    "The sunrise this morning reminded me of Psalm 19:1 — 'The heavens declare the glory of God.' What a Creator!",
    "Just baptized! Best day of my life. Old things have passed away, all things have become new. 2 Cor 5:17",
    "Teaching my kids about David and Goliath tonight. The faith lessons in this story never get old!",
    "Fasting and praying this week for our nation. 2 Chronicles 7:14 — 'If my people who are called by my name...'",
]

PRAYER_DATA = [
    {"title": "Prayer for healing", "description": "Please pray for my mother who is going through chemotherapy. She needs strength and healing. God is able!"},
    {"title": "Guidance needed", "description": "I'm at a crossroads in my career. Praying for God's wisdom and direction. Jeremiah 29:11."},
    {"title": "Prayer for our nation", "description": "Let us lift up our leaders and pray for peace, justice, and righteousness across the land."},
    {"title": "Struggling with faith", "description": "Going through a season of doubt. Please pray that God would strengthen my faith and draw me closer to Him."},
    {"title": "New baby on the way!", "description": "My wife and I are expecting our first child! Praying for a healthy pregnancy and safe delivery. So grateful!"},
    {"title": "Missionaries abroad", "description": "Lifting up our missionaries serving in Southeast Asia. Pray for their safety, provision, and fruitful ministry."},
    {"title": "Prayer for marriage", "description": "Our marriage needs renewal. Praying for healing, forgiveness, and a fresh start rooted in Christ."},
    {"title": "Job search", "description": "Lost my job last month. Trusting God's provision but asking for prayer as I search for new opportunities."},
    {"title": "Church unity", "description": "Praying for unity in our congregation. May we put aside differences and focus on Christ alone."},
    {"title": "Thanksgiving prayer", "description": "Just want to thank God publicly for everything He's done this year. His grace is sufficient!"},
]

COMMENT_TEXTS = [
    "Amen! This is so true. Thank you for sharing!",
    "Praying for you right now 🙏",
    "What a powerful testimony! God is good.",
    "This really spoke to me today. Needed this.",
    "Beautiful words! Keep spreading the light.",
    "I've been through something similar. God is faithful!",
    "So encouraging! Philippians 4:13 is my life verse too.",
    "Thank you for being vulnerable and sharing this.",
    "Yes! Praying with you on this.",
    "Love this community so much. Blessed to be here.",
    "This is exactly what I needed to hear today.",
    "God's timing is always perfect. Trusting Him!",
    "Such an inspiring post! Sharing with my small group.",
    "Wow, this hit different today. Thank you.",
    "Standing in agreement with you in prayer!",
]

REPLY_TEXTS = [
    "Totally agree with you on this!",
    "Great point! I never thought of it that way.",
    "Thank you for the encouragement!",
    "Praying alongside you 🙏",
    "Amen to that!",
    "This is beautiful. God bless you!",
    "So true! Thanks for sharing your perspective.",
]

BIBLE_CONTENT = {
    "sections": [
        {
            "title": "Stories for Little Ones",
            "age_min": 5,
            "age_max": 8,
            "chapters": [
                {
                    "title": "God Creates the World",
                    "pages": [
                        {"title": "In the Beginning", "content": "# In the Beginning\n\nGod made the heavens and the earth. He made the light and separated it from the darkness. He called the light **Day** and the darkness **Night**.\n\n> And God saw that the light was good. — Genesis 1:4\n\nGod made everything beautiful — the sky, the sea, the land, the animals, and finally, He made people!"},
                        {"title": "Adam and Eve", "content": "# Adam and Eve\n\nGod created the first man, **Adam**, from the dust of the ground. Then He made **Eve** to be Adam's partner.\n\nGod placed them in a beautiful garden called **Eden** where they could live happily and take care of all the animals.\n\n> Then the Lord God formed a man from the dust of the ground. — Genesis 2:7"},
                    ],
                },
                {
                    "title": "Noah and the Ark",
                    "pages": [
                        {"title": "God Tells Noah to Build", "content": "# Noah Builds the Ark\n\nGod saw that people on earth had become very wicked. But **Noah** was a good man who loved God.\n\nGod told Noah to build a big boat called an **ark** and to bring two of every animal inside.\n\n> Noah did everything just as God commanded him. — Genesis 6:22"},
                        {"title": "The Rainbow Promise", "content": "# The Rainbow Promise\n\nAfter the flood, God made a **promise** to Noah. He put a beautiful rainbow in the sky.\n\nThe rainbow was a sign that God would never flood the whole earth again.\n\n> I have set my rainbow in the clouds, and it will be the sign of the covenant. — Genesis 9:13"},
                    ],
                },
            ],
        },
        {
            "title": "Adventures in Faith",
            "age_min": 9,
            "age_max": 12,
            "chapters": [
                {
                    "title": "David: A Heart After God",
                    "pages": [
                        {"title": "The Shepherd Boy", "content": "# David the Shepherd Boy\n\n**David** was the youngest of Jesse's sons. While his brothers were tall and strong, David was just a shepherd boy tending his father's sheep.\n\nBut God doesn't look at the outside — He looks at the **heart**.\n\n> The Lord does not look at the things people look at. People look at the outward appearance, but the Lord looks at the heart. — 1 Samuel 16:7"},
                        {"title": "David and Goliath", "content": "# David Faces Goliath\n\nA giant named **Goliath** challenged the army of Israel. Everyone was afraid — except David.\n\nWith just a sling and a stone, and with **faith in God**, David defeated the giant.\n\n> David said to the Philistine, 'You come against me with sword and spear, but I come against you in the name of the Lord Almighty.' — 1 Samuel 17:45"},
                    ],
                },
                {
                    "title": "Daniel's Courage",
                    "pages": [
                        {"title": "The Lions' Den", "content": "# Daniel in the Lions' Den\n\n**Daniel** refused to stop praying to God, even when the king made a law against it.\n\nHe was thrown into a den of hungry lions, but God sent an angel to shut the lions' mouths!\n\n> My God sent his angel, and he shut the mouths of the lions. — Daniel 6:22"},
                    ],
                },
            ],
        },
        {
            "title": "Growing in Christ",
            "age_min": 13,
            "age_max": 17,
            "chapters": [
                {
                    "title": "The Sermon on the Mount",
                    "pages": [
                        {"title": "The Beatitudes", "content": "# The Beatitudes\n\nJesus went up on a mountainside and began to teach His followers what it truly means to be **blessed**.\n\n## The Blessings\n\n- Blessed are the **poor in spirit**, for theirs is the kingdom of heaven\n- Blessed are those who **mourn**, for they will be comforted\n- Blessed are the **meek**, for they will inherit the earth\n- Blessed are those who **hunger and thirst for righteousness**, for they will be filled\n- Blessed are the **merciful**, for they will be shown mercy\n- Blessed are the **pure in heart**, for they will see God\n- Blessed are the **peacemakers**, for they will be called children of God\n\n> — Matthew 5:3-9"},
                        {"title": "Salt and Light", "content": "# Salt and Light\n\nJesus called His followers the **salt of the earth** and the **light of the world**.\n\nSalt preserves and adds flavor. Light dispels darkness. As Christians, we are called to make a difference wherever we go.\n\n> You are the light of the world. A town built on a hill cannot be hidden. — Matthew 5:14\n\n**Question to think about:** How can you be salt and light in your school, family, and community this week?"},
                    ],
                },
            ],
        },
        {
            "title": "Deep Dive: Theology",
            "age_min": 18,
            "age_max": 99,
            "chapters": [
                {
                    "title": "Understanding Justification",
                    "pages": [
                        {"title": "Justified by Faith", "content": "# Justification by Faith\n\nOne of the central doctrines of Christianity is **justification by faith** — the teaching that we are declared righteous before God not by our own works, but through **faith in Jesus Christ**.\n\n## Key Passages\n\n> For it is by grace you have been saved, through faith — and this is not from yourselves, it is the gift of God — not by works, so that no one can boast. — Ephesians 2:8-9\n\n> Therefore, since we have been justified through faith, we have peace with God through our Lord Jesus Christ. — Romans 5:1\n\n## What Justification Means\n\n1. **Legal declaration** — God declares us righteous\n2. **Imputed righteousness** — Christ's righteousness is credited to us\n3. **Once for all** — It is a completed work, not ongoing\n4. **By grace through faith** — Not earned, but received\n\nThis doctrine was central to the Protestant Reformation and remains foundational to evangelical Christianity today."},
                        {"title": "Sanctification", "content": "# The Process of Sanctification\n\nWhile **justification** is a one-time event, **sanctification** is the ongoing process of being made holy — becoming more like Christ in our daily lives.\n\n> And we all, who with unveiled faces contemplate the Lord's glory, are being transformed into his image with ever-increasing glory. — 2 Corinthians 3:18\n\n## Three Aspects of Sanctification\n\n1. **Positional** — We are already set apart in Christ (1 Corinthians 1:2)\n2. **Progressive** — We are being transformed daily (Philippians 1:6)\n3. **Ultimate** — We will be fully sanctified in glory (1 John 3:2)\n\nSanctification requires both **God's work** (Philippians 2:13) and **our effort** (Philippians 2:12). It is a partnership of grace."},
                    ],
                },
            ],
        },
    ]
}

VERSE_DATA = [
    {"ref": "John 3:16", "text": "For God so loved the world that he gave his one and only Son, that whoever believes in him shall not perish but have eternal life."},
    {"ref": "Psalm 23:1", "text": "The Lord is my shepherd, I lack nothing."},
    {"ref": "Jeremiah 29:11", "text": "For I know the plans I have for you, declares the Lord, plans to prosper you and not to harm you, plans to give you hope and a future."},
    {"ref": "Philippians 4:13", "text": "I can do all this through him who gives me strength."},
    {"ref": "Proverbs 3:5-6", "text": "Trust in the Lord with all your heart and lean not on your own understanding; in all your ways submit to him, and he will make your paths straight."},
    {"ref": "Romans 8:28", "text": "And we know that in all things God works for the good of those who love him, who have been called according to his purpose."},
    {"ref": "Isaiah 40:31", "text": "But those who hope in the Lord will renew their strength. They will soar on wings like eagles; they will run and not grow weary, they will walk and not be faint."},
    {"ref": "Psalm 46:10", "text": "He says, 'Be still, and know that I am God; I will be exalted among the nations, I will be exalted in the earth.'"},
    {"ref": "Matthew 28:20", "text": "And surely I am with you always, to the very end of the age."},
    {"ref": "Joshua 1:9", "text": "Have I not commanded you? Be strong and courageous. Do not be afraid; do not be discouraged, for the Lord your God will be with you wherever you go."},
    {"ref": "Psalm 119:105", "text": "Your word is a lamp for my feet, a light on my path."},
    {"ref": "Romans 12:2", "text": "Do not conform to the pattern of this world, but be transformed by the renewing of your mind."},
    {"ref": "Galatians 5:22-23", "text": "But the fruit of the Spirit is love, joy, peace, forbearance, kindness, goodness, faithfulness, gentleness and self-control."},
    {"ref": "1 Corinthians 13:4", "text": "Love is patient, love is kind. It does not envy, it does not boast, it is not proud."},
]

CHAT_MESSAGES = [
    "Hey! How are you doing?",
    "I'm good, thanks! Just got back from church.",
    "That's awesome! What was the sermon about?",
    "It was about the parable of the sower. Really good!",
    "Oh I love that one. Matthew 13 right?",
    "Yes! Are you coming to Bible study on Wednesday?",
    "Definitely! I'm bringing snacks this time 😄",
    "Perfect! See you there.",
    "Have you read the new devotional James posted?",
    "Not yet, I'll check it out today!",
    "It's really encouraging. About trusting God's timing.",
    "That's something I need to hear right now honestly.",
    "We all do sometimes. Praying for you!",
    "Thank you so much, that means a lot 🙏",
    "[sticker:1]",
    "[sticker:5]",
    "[sticker:12]",
    "Good morning! Did you do your devotional today?",
    "Yes! Psalm 23 — such a comforting chapter.",
    "The Lord is my shepherd — one of my favorites!",
]


class Command(BaseCommand):
    help = "Seed the database with realistic test data"

    def add_arguments(self, parser: Any) -> None:
        parser.add_argument(
            "--flush",
            action="store_true",
            help="Flush the database before seeding",
        )

    def handle(self, *args: Any, **options: Any) -> None:
        if options["flush"]:
            self.stdout.write("Flushing database...")
            from django.core.management import call_command

            call_command("flush", "--no-input")
            self.stdout.write(self.style.SUCCESS("Database flushed."))

        self.stdout.write("Seeding database...")

        users = self._create_users()
        self._create_follows(users)
        posts = self._create_posts(users)
        prayers = self._create_prayers(users)
        self._create_comments_and_replies(users, posts, prayers)
        self._create_reactions(users, posts, prayers)
        self._create_bible_content()
        self._create_verses()
        self._create_conversations_and_messages(users)
        self._create_notifications(users)
        self._create_admin(users)
        self._create_boost_tiers()

        self.stdout.write(self.style.SUCCESS("Seed complete!"))

    def _create_users(self) -> list:
        from apps.accounts.models import User

        users = []
        for data in USERS_DATA:
            user, created = User.objects.get_or_create(
                email=data["email"],
                defaults={
                    "full_name": data["full_name"],
                    "gender": data["gender"],
                    "country": data["country"],
                    "bio": data["bio"],
                    "date_of_birth": data["date_of_birth"],
                    "preferred_language": "en",
                    "is_active": True,
                    "is_email_verified": True,
                },
            )
            if created:
                user.set_password(PASSWORD)
                user.save(update_fields=["password"])
            users.append(user)

        self.stdout.write(f"  Users: {len(users)}")
        return users

    def _create_follows(self, users: list) -> None:
        from apps.accounts.models import FollowRelationship

        count = 0
        for user in users:
            to_follow = random.sample(
                [u for u in users if u != user], k=random.randint(3, 8)
            )
            for target in to_follow:
                _, created = FollowRelationship.objects.get_or_create(
                    follower=user, following=target
                )
                if created:
                    count += 1

        from django.db.models import Count

        from apps.accounts.models import User

        for user in users:
            fc = FollowRelationship.objects.filter(following=user).count()
            fgc = FollowRelationship.objects.filter(follower=user).count()
            User.objects.filter(pk=user.pk).update(
                follower_count=fc, following_count=fgc
            )

        self.stdout.write(f"  Follows: {count}")

    def _create_posts(self, users: list) -> list:
        from apps.social.models import Post

        posts = []
        now = timezone.now()
        for i, text in enumerate(POST_TEXTS):
            author = users[i % len(users)]
            post, created = Post.objects.get_or_create(
                author=author,
                text_content=text,
                defaults={
                    "created_at": now - datetime.timedelta(hours=random.randint(1, 720)),
                },
            )
            posts.append(post)

        from apps.accounts.models import User

        for user in users:
            pc = Post.objects.filter(author=user).count()
            User.objects.filter(pk=user.pk).update(post_count=pc)

        self.stdout.write(f"  Posts: {len(posts)}")
        return posts

    def _create_prayers(self, users: list) -> list:
        from apps.social.models import Prayer

        prayers = []
        now = timezone.now()
        for i, data in enumerate(PRAYER_DATA):
            author = users[i % len(users)]
            prayer, _ = Prayer.objects.get_or_create(
                author=author,
                title=data["title"],
                defaults={
                    "description": data["description"],
                    "created_at": now - datetime.timedelta(hours=random.randint(1, 480)),
                },
            )
            prayers.append(prayer)

        from apps.accounts.models import User

        for user in users:
            pc = Prayer.objects.filter(author=user).count()
            User.objects.filter(pk=user.pk).update(prayer_count=pc)

        self.stdout.write(f"  Prayers: {len(prayers)}")
        return prayers

    def _create_comments_and_replies(
        self, users: list, posts: list, prayers: list
    ) -> None:
        from apps.social.models import Comment, Post, Prayer, Reply

        post_ct = ContentType.objects.get_for_model(Post)
        prayer_ct = ContentType.objects.get_for_model(Prayer)

        comment_count = 0
        reply_count = 0

        for post in posts:
            n_comments = random.randint(1, 5)
            commenters = random.sample(users, k=min(n_comments, len(users)))
            for commenter in commenters:
                comment = Comment.objects.create(
                    user=commenter,
                    content_type=post_ct,
                    object_id=post.pk,
                    text=random.choice(COMMENT_TEXTS),
                )
                comment_count += 1

                if random.random() > 0.5:
                    replier = random.choice([u for u in users if u != commenter])
                    Reply.objects.create(
                        user=replier,
                        comment=comment,
                        text=random.choice(REPLY_TEXTS),
                    )
                    reply_count += 1

            Post.objects.filter(pk=post.pk).update(
                comment_count=Comment.objects.filter(
                    content_type=post_ct, object_id=post.pk
                ).count()
            )

        for prayer in prayers:
            n_comments = random.randint(1, 3)
            commenters = random.sample(users, k=min(n_comments, len(users)))
            for commenter in commenters:
                Comment.objects.create(
                    user=commenter,
                    content_type=prayer_ct,
                    object_id=prayer.pk,
                    text=random.choice(COMMENT_TEXTS),
                )
                comment_count += 1

            Prayer.objects.filter(pk=prayer.pk).update(
                comment_count=Comment.objects.filter(
                    content_type=prayer_ct, object_id=prayer.pk
                ).count()
            )

        self.stdout.write(f"  Comments: {comment_count}, Replies: {reply_count}")

    def _create_reactions(self, users: list, posts: list, prayers: list) -> None:
        from apps.social.models import Post, Prayer, Reaction

        post_ct = ContentType.objects.get_for_model(Post)
        prayer_ct = ContentType.objects.get_for_model(Prayer)
        emoji_types = ["praying_hands", "heart", "fire", "amen", "cross"]

        count = 0
        for post in posts:
            reactors = random.sample(users, k=random.randint(2, 8))
            for reactor in reactors:
                _, created = Reaction.objects.get_or_create(
                    user=reactor,
                    content_type=post_ct,
                    object_id=post.pk,
                    defaults={"emoji_type": random.choice(emoji_types)},
                )
                if created:
                    count += 1
            Post.objects.filter(pk=post.pk).update(
                reaction_count=Reaction.objects.filter(
                    content_type=post_ct, object_id=post.pk
                ).count()
            )

        for prayer in prayers:
            reactors = random.sample(users, k=random.randint(2, 6))
            for reactor in reactors:
                _, created = Reaction.objects.get_or_create(
                    user=reactor,
                    content_type=prayer_ct,
                    object_id=prayer.pk,
                    defaults={"emoji_type": random.choice(emoji_types)},
                )
                if created:
                    count += 1
            Prayer.objects.filter(pk=prayer.pk).update(
                reaction_count=Reaction.objects.filter(
                    content_type=prayer_ct, object_id=prayer.pk
                ).count()
            )

        self.stdout.write(f"  Reactions: {count}")

    def _create_bible_content(self) -> None:
        from apps.bible.models import SegregatedChapter, SegregatedPage, SegregatedSection

        section_count = 0
        chapter_count = 0
        page_count = 0

        for s_order, section_data in enumerate(BIBLE_CONTENT["sections"]):
            section, _ = SegregatedSection.objects.get_or_create(
                title=section_data["title"],
                defaults={
                    "age_min": section_data["age_min"],
                    "age_max": section_data["age_max"],
                    "order": s_order,
                    "is_active": True,
                },
            )
            section_count += 1

            for c_order, chapter_data in enumerate(section_data["chapters"]):
                chapter, _ = SegregatedChapter.objects.get_or_create(
                    section=section,
                    title=chapter_data["title"],
                    defaults={"order": c_order, "is_active": True},
                )
                chapter_count += 1

                for p_order, page_data in enumerate(chapter_data["pages"]):
                    SegregatedPage.objects.get_or_create(
                        chapter=chapter,
                        title=page_data["title"],
                        defaults={
                            "content": page_data["content"],
                            "order": p_order,
                            "is_active": True,
                        },
                    )
                    page_count += 1

        self.stdout.write(
            f"  Bible: {section_count} sections, {chapter_count} chapters, {page_count} pages"
        )

    def _create_verses(self) -> None:
        from apps.verse_of_day.models import VerseFallbackPool, VerseOfDay

        today = timezone.now().date()
        vod_count = 0
        for i, verse in enumerate(VERSE_DATA[:7]):
            display_date = today - datetime.timedelta(days=i)
            _, created = VerseOfDay.objects.get_or_create(
                display_date=display_date,
                defaults={
                    "bible_reference": verse["ref"],
                    "verse_text": verse["text"],
                    "is_active": True,
                },
            )
            if created:
                vod_count += 1

        pool_count = 0
        for verse in VERSE_DATA:
            _, created = VerseFallbackPool.objects.get_or_create(
                bible_reference=verse["ref"],
                defaults={
                    "verse_text": verse["text"],
                    "is_active": True,
                },
            )
            if created:
                pool_count += 1

        self.stdout.write(f"  Verses: {vod_count} scheduled, {pool_count} in fallback pool")

    def _create_conversations_and_messages(self, users: list) -> None:
        from apps.chat.models import Conversation, Message

        conv_count = 0
        msg_count = 0

        pairs = [
            (0, 1), (0, 2), (0, 4), (1, 3), (1, 5),
            (2, 6), (3, 7), (4, 8), (5, 9), (6, 10),
            (7, 11), (8, 12), (9, 13), (10, 14), (2, 5),
        ]

        now = timezone.now()

        for idx_a, idx_b in pairs:
            if idx_a >= len(users) or idx_b >= len(users):
                continue

            user_a, user_b = users[idx_a], users[idx_b]
            u1, u2 = (user_a, user_b) if user_a.pk < user_b.pk else (user_b, user_a)

            conv, created = Conversation.objects.get_or_create(
                user1=u1, user2=u2
            )
            if created:
                conv_count += 1

            n_messages = random.randint(4, 10)
            msg_pool = random.sample(CHAT_MESSAGES, k=min(n_messages, len(CHAT_MESSAGES)))
            last_msg = None

            for j, text in enumerate(msg_pool):
                sender = user_a if j % 2 == 0 else user_b
                msg = Message.objects.create(
                    conversation=conv,
                    sender=sender,
                    text=text,
                    is_read=j < len(msg_pool) - 2,
                )
                msg_count += 1
                last_msg = msg

            if last_msg:
                Conversation.objects.filter(pk=conv.pk).update(
                    last_message_text=last_msg.text[:1000],
                    last_message_at=last_msg.created_at,
                    last_message_sender=last_msg.sender,
                )

        self.stdout.write(f"  Conversations: {conv_count}, Messages: {msg_count}")

    def _create_notifications(self, users: list) -> None:
        from apps.notifications.models import Notification

        count = 0
        types = [
            ("follow", "{sender} started following you"),
            ("reaction", "{sender} reacted to your post"),
            ("comment", "{sender} commented on your post"),
            ("prayer_comment", "{sender} commented on your prayer"),
        ]

        for user in users[:8]:
            senders = random.sample([u for u in users if u != user], k=3)
            for sender in senders:
                ntype, body_tpl = random.choice(types)
                Notification.objects.create(
                    recipient=user,
                    sender=sender,
                    notification_type=ntype,
                    title=ntype.replace("_", " ").title(),
                    body=body_tpl.format(sender=sender.full_name),
                    is_read=random.random() > 0.4,
                )
                count += 1

        self.stdout.write(f"  Notifications: {count}")

    def _create_admin(self, users: list) -> None:
        from apps.accounts.models import User
        from apps.admin_panel.models import AdminRole

        admin_user = users[5]
        User.objects.filter(pk=admin_user.pk).update(is_staff=True)

        AdminRole.objects.get_or_create(
            user=admin_user,
            defaults={"role": "super_admin"},
        )

        self.stdout.write(f"  Admin: {admin_user.email} (super_admin)")

    def _create_boost_tiers(self) -> None:
        from apps.admin_panel.models import BoostTier

        tiers = [
            {"name": "Basic Boost", "apple_product_id": "boost_basic", "google_product_id": "boost_basic", "duration_days": 3, "display_price": "$2.99"},
            {"name": "Standard Boost", "apple_product_id": "boost_standard", "google_product_id": "boost_standard", "duration_days": 7, "display_price": "$4.99"},
            {"name": "Premium Boost", "apple_product_id": "boost_premium", "google_product_id": "boost_premium", "duration_days": 14, "display_price": "$9.99"},
        ]

        count = 0
        for tier in tiers:
            _, created = BoostTier.objects.get_or_create(
                apple_product_id=tier["apple_product_id"],
                defaults=tier,
            )
            if created:
                count += 1

        self.stdout.write(f"  Boost tiers: {count}")
