# Bibleway Backend API Reference

Complete API documentation for the Bibleway backend. All endpoints are served under the base URL `/api/v1/`.

---

## Table of Contents

- [Conventions](#conventions)
- [Authentication](#authentication)
- [Accounts](#accounts)
- [Social](#social)
- [Bible](#bible)
- [Shop](#shop)
- [Notifications](#notifications)
- [Analytics](#analytics)
- [Verse of the Day](#verse-of-the-day)
- [Admin Panel](#admin-panel)
- [Health Check](#health-check)
- [Reference](#reference)
  - [Password Requirements](#password-requirements)
  - [Supported Languages](#supported-languages)
  - [Rate Limits](#rate-limits)
  - [Pagination Formats](#pagination-formats)
  - [HTTP Status Codes](#http-status-codes)
  - [Authentication Flow](#authentication-flow)
  - [Admin Role Permissions Matrix](#admin-role-permissions-matrix)

---

## Conventions

### Response Envelope

Every successful response is wrapped in a standard envelope:

```json
{
  "message": "Human-readable description of the result",
  "data": { }
}
```

For list endpoints with pagination, `data` contains the paginated structure (see [Pagination Formats](#pagination-formats)).

### Error Envelope

All error responses use the following shape:

```json
{
  "message": "Error description"
}
```

Validation errors (400) may include field-level detail:

```json
{
  "message": "Validation error",
  "data": {
    "email": ["This field is required."],
    "password": ["Password must be at least 8 characters."]
  }
}
```

### Authentication Header

All endpoints marked **IsAuthenticated** require:

```
Authorization: Bearer <access_token>
```

### Content Types

- JSON endpoints: `Content-Type: application/json`
- File upload endpoints: `Content-Type: multipart/form-data`

---

## Authentication

JWT-based authentication via Simple JWT.

| Property        | Value                      |
| --------------- | -------------------------- |
| Access lifetime | 15 minutes                 |
| Refresh lifetime| 30 days                    |
| Rotation        | Enabled (new refresh on use)|
| Blacklisting    | Enabled                    |
| Header format   | `Authorization: Bearer <token>` |

See [Authentication Flow](#authentication-flow) for the full lifecycle.

---

## Accounts

Base path: `/api/v1/accounts/`

### POST `/api/v1/accounts/register/`

Register a new user account. Sends a 6-digit OTP to the provided email for verification.

| Property  | Value            |
| --------- | ---------------- |
| Auth      | AllowAny         |
| Throttle  | AuthRateThrottle (10/min) |

**Request Body**

| Field              | Type   | Required | Constraints                                                                 |
| ------------------ | ------ | -------- | --------------------------------------------------------------------------- |
| email              | string | Yes      | Max 255 characters. Must be a valid email address.                          |
| password           | string | Yes      | 8-128 characters. See [Password Requirements](#password-requirements).       |
| full_name          | string | Yes      | Max 150 characters.                                                         |
| date_of_birth      | string | Yes      | Format `YYYY-MM-DD`. Age must be 13-120. Must not be a future date.          |
| gender             | string | Yes      | One of: `male`, `female`, `prefer_not_to_say`.                               |
| preferred_language | string | No       | Default `"en"`. See [Supported Languages](#supported-languages).             |
| country            | string | Yes      | Max 100 characters.                                                         |
| phone_number       | string | No       | Default `""`. Max 20 characters. Must match phone number regex if provided.  |

**Response: 201 Created**

```json
{
  "message": "Registration successful. Please verify your email.",
  "data": {
    "id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
    "email": "user@example.com",
    "full_name": "John Doe",
    "date_of_birth": "1995-06-15",
    "gender": "male",
    "preferred_language": "en",
    "country": "United States",
    "phone_number": "+1234567890",
    "profile_photo": null,
    "bio": "",
    "is_email_verified": false,
    "date_joined": "2026-03-26T12:00:00Z",
    "age": 30,
    "follower_count": 0,
    "following_count": 0,
    "post_count": 0,
    "prayer_count": 0,
    "follow_status": "self"
  }
}
```

**Error Responses**

| Status | Condition                    |
| ------ | ---------------------------- |
| 400    | Validation errors            |
| 409    | Email already registered     |
| 429    | Rate limit exceeded          |

---

### POST `/api/v1/accounts/login/`

Authenticate a user and receive JWT tokens.

| Property  | Value            |
| --------- | ---------------- |
| Auth      | AllowAny         |
| Throttle  | AuthRateThrottle (10/min) |

**Request Body**

| Field    | Type   | Required | Constraints |
| -------- | ------ | -------- | ----------- |
| email    | string | Yes      |             |
| password | string | Yes      |             |

**Response: 200 OK**

```json
{
  "message": "Login successful.",
  "data": {
    "access": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
    "refresh": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
    "user_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890"
  }
}
```

**Error Responses**

| Status | Condition                                         |
| ------ | ------------------------------------------------- |
| 400    | Invalid credentials or email not yet verified     |
| 429    | Rate limit exceeded                               |

---

### POST `/api/v1/accounts/logout/`

Blacklist the refresh token to log out the user.

| Property  | Value           |
| --------- | --------------- |
| Auth      | IsAuthenticated |
| Throttle  | None            |

**Request Body**

| Field   | Type   | Required | Constraints |
| ------- | ------ | -------- | ----------- |
| refresh | string | Yes      | Valid, non-blacklisted refresh token. |

**Response: 200 OK**

```json
{
  "message": "Logout successful."
}
```

**Error Responses**

| Status | Condition                    |
| ------ | ---------------------------- |
| 400    | Missing or invalid token     |
| 401    | Not authenticated            |

---

### POST `/api/v1/accounts/token/refresh/`

Obtain a new access/refresh token pair using a valid refresh token. The old refresh token is rotated (blacklisted) and a new one is issued.

| Property  | Value    |
| --------- | -------- |
| Auth      | AllowAny |
| Throttle  | None     |

**Request Body**

| Field   | Type   | Required | Constraints |
| ------- | ------ | -------- | ----------- |
| refresh | string | Yes      | Valid, non-blacklisted refresh token. |

**Response: 200 OK**

```json
{
  "message": "Token refreshed.",
  "data": {
    "access": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
    "refresh": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."
  }
}
```

**Error Responses**

| Status | Condition                               |
| ------ | --------------------------------------- |
| 400    | Invalid, expired, or blacklisted token  |

---

### POST `/api/v1/accounts/verify-email/`

Verify a user's email address using the 6-digit OTP sent during registration.

| Property  | Value                       |
| --------- | --------------------------- |
| Auth      | AllowAny                    |
| Throttle  | OTPRateThrottle (5/min)     |

**Request Body**

| Field    | Type   | Required | Constraints                |
| -------- | ------ | -------- | -------------------------- |
| email    | string | Yes      | Must match a registered account. |
| otp_code | string | Yes      | Exactly 6 digits.          |

**Response: 200 OK**

```json
{
  "message": "Email verified successfully.",
  "data": {
    "id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
    "email": "user@example.com",
    "full_name": "John Doe",
    "date_of_birth": "1995-06-15",
    "gender": "male",
    "preferred_language": "en",
    "country": "United States",
    "phone_number": "+1234567890",
    "profile_photo": null,
    "bio": "",
    "is_email_verified": true,
    "date_joined": "2026-03-26T12:00:00Z",
    "age": 30,
    "follower_count": 0,
    "following_count": 0,
    "post_count": 0,
    "prayer_count": 0,
    "follow_status": "self"
  }
}
```

**Error Responses**

| Status | Condition                               |
| ------ | --------------------------------------- |
| 400    | Invalid OTP, expired OTP, max attempts exceeded |
| 404    | No account found for the given email    |
| 409    | Email is already verified               |
| 429    | Rate limit exceeded                     |

---

### POST `/api/v1/accounts/auth/resend-otp/`

Resend the OTP verification code to the provided email. Always returns 200 regardless of whether the email exists, to prevent user enumeration.

| Property  | Value                       |
| --------- | --------------------------- |
| Auth      | AllowAny                    |
| Throttle  | OTPRateThrottle (5/min)     |

**Request Body**

| Field | Type   | Required | Constraints |
| ----- | ------ | -------- | ----------- |
| email | string | Yes      |             |

**Response: 200 OK**

```json
{
  "message": "If an account exists with this email, a new OTP has been sent."
}
```

**Error Responses**

| Status | Condition           |
| ------ | ------------------- |
| 429    | Rate limit exceeded |

---

### POST `/api/v1/accounts/password-reset/`

Request a password reset OTP. Always returns 200 regardless of whether the email exists, to prevent user enumeration.

| Property  | Value                       |
| --------- | --------------------------- |
| Auth      | AllowAny                    |
| Throttle  | OTPRateThrottle (5/min)     |

**Request Body**

| Field | Type   | Required | Constraints |
| ----- | ------ | -------- | ----------- |
| email | string | Yes      |             |

**Response: 200 OK**

```json
{
  "message": "If an account exists with this email, a password reset OTP has been sent."
}
```

**Error Responses**

| Status | Condition           |
| ------ | ------------------- |
| 429    | Rate limit exceeded |

---

### POST `/api/v1/accounts/password-reset/confirm/`

Confirm password reset using the OTP and set a new password. Invalidates all existing sessions (all refresh tokens are blacklisted).

| Property  | Value                       |
| --------- | --------------------------- |
| Auth      | AllowAny                    |
| Throttle  | OTPRateThrottle (5/min)     |

**Request Body**

| Field        | Type   | Required | Constraints                                                             |
| ------------ | ------ | -------- | ----------------------------------------------------------------------- |
| email        | string | Yes      |                                                                         |
| otp_code     | string | Yes      | Exactly 6 digits.                                                       |
| new_password | string | Yes      | 8-128 characters. See [Password Requirements](#password-requirements).   |

**Response: 200 OK**

```json
{
  "message": "Password reset successful. All sessions have been invalidated."
}
```

**Error Responses**

| Status | Condition                              |
| ------ | -------------------------------------- |
| 400    | Invalid OTP or weak password           |
| 404    | No account found for the given email   |
| 429    | Rate limit exceeded                    |

---

### POST `/api/v1/accounts/change-password/`

Change the password for the currently authenticated user. Invalidates all existing sessions.

| Property  | Value           |
| --------- | --------------- |
| Auth      | IsAuthenticated |
| Throttle  | None            |

**Request Body**

| Field        | Type   | Required | Constraints                                                             |
| ------------ | ------ | -------- | ----------------------------------------------------------------------- |
| old_password | string | Yes      | Must match the user's current password.                                 |
| new_password | string | Yes      | 8-128 characters. See [Password Requirements](#password-requirements).   |

**Response: 200 OK**

```json
{
  "message": "Password changed successfully. All sessions have been invalidated."
}
```

**Error Responses**

| Status | Condition                         |
| ------ | --------------------------------- |
| 400    | Wrong old password or weak new password |
| 401    | Not authenticated                 |

---

### GET `/api/v1/accounts/profile/`

Retrieve the authenticated user's own profile. Includes PII fields (email, phone, date of birth, verification status). Response is cached for 60 seconds.

| Property  | Value           |
| --------- | --------------- |
| Auth      | IsAuthenticated |
| Throttle  | None            |
| Cache     | 60 seconds      |

**Response: 200 OK**

```json
{
  "message": "Profile retrieved.",
  "data": {
    "id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
    "email": "user@example.com",
    "full_name": "John Doe",
    "date_of_birth": "1995-06-15",
    "gender": "male",
    "preferred_language": "en",
    "country": "United States",
    "phone_number": "+1234567890",
    "profile_photo": "https://utfs.io/f/abc123.jpg",
    "bio": "A short bio.",
    "is_email_verified": true,
    "date_joined": "2026-03-26T12:00:00Z",
    "age": 30,
    "follower_count": 42,
    "following_count": 18,
    "post_count": 7,
    "prayer_count": 3,
    "follow_status": "self"
  }
}
```

**Error Responses**

| Status | Condition       |
| ------ | --------------- |
| 401    | Not authenticated |

---

### PUT/PATCH `/api/v1/accounts/profile/`

Update the authenticated user's profile. `PUT` requires all editable fields; `PATCH` accepts any subset. Invalidates the profile cache on success.

| Property  | Value           |
| --------- | --------------- |
| Auth      | IsAuthenticated |
| Throttle  | None            |

**Request Body**

| Field              | Type   | Required (PUT) | Constraints                                                              |
| ------------------ | ------ | -------------- | ------------------------------------------------------------------------ |
| full_name          | string | Yes            | Max 150 characters.                                                      |
| bio                | string | Yes            | Max 250 characters. Blank allowed.                                       |
| profile_photo      | file   | No             | Image file (multipart upload).                                           |
| preferred_language | string | Yes            | See [Supported Languages](#supported-languages).                         |
| country            | string | Yes            | Max 100 characters.                                                      |
| phone_number       | string | Yes            | Max 20 characters. Blank allowed. Must match phone format if non-blank.  |
| date_of_birth      | string | Yes            | Format `YYYY-MM-DD`. Age must be 13-120. Must not be a future date.       |

For `PATCH`, all fields are optional.

**Response: 200 OK**

Returns the updated UserProfile object (same shape as `GET /profile/`).

**Error Responses**

| Status | Condition                                 |
| ------ | ----------------------------------------- |
| 400    | No valid fields provided or validation failure |
| 401    | Not authenticated                         |

---

### GET `/api/v1/accounts/users/<uuid:user_id>/`

Retrieve another user's public profile. PII fields (email, phone_number, date_of_birth, is_email_verified) are stripped from the response. The `follow_status` field indicates the requesting user's relationship to the target.

| Property  | Value                      |
| --------- | -------------------------- |
| Auth      | IsAuthenticated            |
| Permission| IsNotBlocked               |

**Response: 200 OK**

```json
{
  "message": "User profile retrieved.",
  "data": {
    "id": "b2c3d4e5-f6a7-8901-bcde-f12345678901",
    "full_name": "Jane Smith",
    "gender": "female",
    "preferred_language": "en",
    "country": "Canada",
    "profile_photo": "https://utfs.io/f/def456.jpg",
    "bio": "Lover of scripture.",
    "date_joined": "2026-01-15T08:30:00Z",
    "age": 28,
    "follower_count": 120,
    "following_count": 55,
    "post_count": 14,
    "prayer_count": 6,
    "follow_status": "following"
  }
}
```

The `follow_status` field has three possible values:

| Value       | Meaning                                   |
| ----------- | ----------------------------------------- |
| `"self"`    | The requesting user is viewing their own profile |
| `"following"` | The requesting user follows this user   |
| `"none"`    | No follow relationship exists             |

**Error Responses**

| Status | Condition                              |
| ------ | -------------------------------------- |
| 401    | Not authenticated                      |
| 403    | One user has blocked the other         |
| 404    | User not found                         |

---

### GET `/api/v1/accounts/users/search/`

Search for users by name or country. Only returns active, email-verified users.

| Property   | Value                              |
| ---------- | ---------------------------------- |
| Auth       | IsAuthenticated                    |
| Pagination | StandardPageNumberPagination (20/page) |

**Query Parameters**

| Param   | Type   | Required | Description               |
| ------- | ------ | -------- | ------------------------- |
| q       | string | No       | Search by full name (partial match). |
| country | string | No       | Filter by country.        |

**Response: 200 OK**

```json
{
  "message": "Search results.",
  "data": {
    "count": 2,
    "next": null,
    "previous": null,
    "results": [
      {
        "id": "b2c3d4e5-f6a7-8901-bcde-f12345678901",
        "full_name": "Jane Smith",
        "profile_photo": "https://utfs.io/f/def456.jpg",
        "bio": "Lover of scripture.",
        "age": 28
      }
    ]
  }
}
```

---

### POST `/api/v1/accounts/users/<uuid:user_id>/follow/`

Follow a user.

| Property   | Value           |
| ---------- | --------------- |
| Auth       | IsAuthenticated |
| Permission | IsNotBlocked    |

**Response: 201 Created**

```json
{
  "message": "Now following this user.",
  "data": {
    "id": "c3d4e5f6-a7b8-9012-cdef-123456789012",
    "follower": {
      "id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
      "full_name": "John Doe",
      "profile_photo": null,
      "bio": "",
      "age": 30
    },
    "following": {
      "id": "b2c3d4e5-f6a7-8901-bcde-f12345678901",
      "full_name": "Jane Smith",
      "profile_photo": "https://utfs.io/f/def456.jpg",
      "bio": "Lover of scripture.",
      "age": 28
    },
    "created_at": "2026-03-26T14:00:00Z"
  }
}
```

**Error Responses**

| Status | Condition              |
| ------ | ---------------------- |
| 400    | Cannot follow yourself |
| 401    | Not authenticated      |
| 403    | One user has blocked the other |
| 404    | User not found         |
| 409    | Already following      |

---

### DELETE `/api/v1/accounts/users/<uuid:user_id>/follow/`

Unfollow a user.

| Property   | Value           |
| ---------- | --------------- |
| Auth       | IsAuthenticated |
| Permission | IsNotBlocked    |

**Response: 204 No Content**

Empty response body.

**Error Responses**

| Status | Condition              |
| ------ | ---------------------- |
| 401    | Not authenticated      |
| 403    | Blocked                |
| 404    | Not currently following this user |

---

### GET `/api/v1/accounts/users/<uuid:user_id>/followers/`

List a user's followers.

| Property   | Value                              |
| ---------- | ---------------------------------- |
| Auth       | IsAuthenticated                    |
| Pagination | StandardPageNumberPagination (20/page) |

**Response: 200 OK**

Paginated list of FollowRelationship objects (same shape as the follow response).

---

### GET `/api/v1/accounts/users/<uuid:user_id>/following/`

List users that a user is following.

| Property   | Value                              |
| ---------- | ---------------------------------- |
| Auth       | IsAuthenticated                    |
| Pagination | StandardPageNumberPagination (20/page) |

**Response: 200 OK**

Paginated list of FollowRelationship objects.

---

### POST `/api/v1/accounts/users/<uuid:user_id>/block/`

Block a user. Automatically removes all follow relationships between both users (in both directions).

| Property   | Value           |
| ---------- | --------------- |
| Auth       | IsAuthenticated |

**Response: 201 Created**

```json
{
  "message": "User blocked.",
  "data": {
    "id": "d4e5f6a7-b8c9-0123-defa-234567890123",
    "blocked": {
      "id": "b2c3d4e5-f6a7-8901-bcde-f12345678901",
      "full_name": "Jane Smith",
      "profile_photo": "https://utfs.io/f/def456.jpg",
      "bio": "Lover of scripture.",
      "age": 28
    },
    "created_at": "2026-03-26T14:05:00Z"
  }
}
```

**Error Responses**

| Status | Condition              |
| ------ | ---------------------- |
| 400    | Cannot block yourself  |
| 401    | Not authenticated      |
| 404    | User not found         |
| 409    | Already blocked        |

---

### DELETE `/api/v1/accounts/users/<uuid:user_id>/block/`

Unblock a user.

| Property   | Value           |
| ---------- | --------------- |
| Auth       | IsAuthenticated |

**Response: 204 No Content**

Empty response body.

**Error Responses**

| Status | Condition                    |
| ------ | ---------------------------- |
| 401    | Not authenticated            |
| 404    | User is not currently blocked |

---

### GET `/api/v1/accounts/blocked-users/`

List all users blocked by the authenticated user.

| Property   | Value                              |
| ---------- | ---------------------------------- |
| Auth       | IsAuthenticated                    |
| Pagination | StandardPageNumberPagination (20/page) |

**Response: 200 OK**

Paginated list of BlockRelationship objects (same shape as the block response).

---

## Social

Base path: `/api/v1/social/`

### GET `/api/v1/social/posts/`

List posts in the feed. Boosted posts are interspersed according to the BoostedFeedCursorPagination algorithm.

| Property   | Value                                |
| ---------- | ------------------------------------ |
| Auth       | IsAuthenticated                      |
| Pagination | BoostedFeedCursorPagination (cursor) |

**Query Parameters**

| Param  | Type   | Required | Description                          |
| ------ | ------ | -------- | ------------------------------------ |
| author | uuid   | No       | Filter posts by author ID.           |
| cursor | string | No       | Cursor token for next/previous page. |

**Response: 200 OK**

```json
{
  "message": "Posts retrieved.",
  "data": {
    "next": "https://api.example.com/api/v1/social/posts/?cursor=cD0yMDI2...",
    "previous": null,
    "results": [
      {
        "id": "e5f6a7b8-c9d0-1234-efab-345678901234",
        "author": {
          "id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
          "full_name": "John Doe",
          "profile_photo": null,
          "age": 30
        },
        "text_content": "Blessed is the one who trusts in the Lord.",
        "is_boosted": false,
        "media": [
          {
            "id": "f6a7b8c9-d0e1-2345-fabc-456789012345",
            "file": "https://utfs.io/f/media123.jpg",
            "media_type": "image",
            "order": 0
          }
        ],
        "reaction_count": 12,
        "comment_count": 3,
        "user_reaction": "heart",
        "created_at": "2026-03-26T10:00:00Z"
      }
    ]
  }
}
```

---

### POST `/api/v1/social/posts/`

Create a new post. Supports text, images, and video. A post may contain up to 10 images or 1 video (not both).

| Property  | Value           |
| --------- | --------------- |
| Auth      | IsAuthenticated |

**Request Body**

| Field        | Type           | Required | Constraints                                          |
| ------------ | -------------- | -------- | ---------------------------------------------------- |
| text_content | string         | No       | Max 2000 characters.                                 |
| media_keys   | array[string]  | No       | UploadThing file keys. Max 10 items.                 |
| media_types  | array[string]  | No       | Parallel array. Each value: `"image"` or `"video"`.  |
| media_files  | array[file]    | No       | Direct file uploads. Max 10 items.                   |

At least `text_content` or media must be provided. Media constraint: max 1 video OR max 10 images per post.

**Response: 201 Created**

```json
{
  "message": "Post created.",
  "data": {
    "id": "e5f6a7b8-c9d0-1234-efab-345678901234",
    "author": {
      "id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
      "full_name": "John Doe",
      "profile_photo": null,
      "age": 30
    },
    "text_content": "Blessed is the one who trusts in the Lord.",
    "is_boosted": false,
    "media": [
      {
        "id": "f6a7b8c9-d0e1-2345-fabc-456789012345",
        "file": "https://utfs.io/f/media123.jpg",
        "media_type": "image",
        "order": 0
      }
    ],
    "reaction_count": 0,
    "comment_count": 0,
    "user_reaction": null,
    "created_at": "2026-03-26T14:30:00Z",
    "updated_at": "2026-03-26T14:30:00Z"
  }
}
```

---

### GET `/api/v1/social/posts/<uuid:pk>/`

Retrieve a single post's full details.

| Property  | Value           |
| --------- | --------------- |
| Auth      | IsAuthenticated |

**Response: 200 OK**

Returns a PostDetail object:

```json
{
  "message": "Post retrieved.",
  "data": {
    "id": "e5f6a7b8-c9d0-1234-efab-345678901234",
    "author": {
      "id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
      "full_name": "John Doe",
      "profile_photo": null,
      "age": 30
    },
    "text_content": "Blessed is the one who trusts in the Lord.",
    "is_boosted": false,
    "media": [],
    "reaction_count": 12,
    "comment_count": 3,
    "user_reaction": "heart",
    "created_at": "2026-03-26T10:00:00Z",
    "updated_at": "2026-03-26T10:00:00Z"
  }
}
```

**Error Responses**

| Status | Condition       |
| ------ | --------------- |
| 401    | Not authenticated |
| 404    | Post not found  |

---

### DELETE `/api/v1/social/posts/<uuid:pk>/`

Delete a post. Only the post owner may delete it.

| Property   | Value              |
| ---------- | ------------------ |
| Auth       | IsAuthenticated    |
| Permission | IsOwnerOrReadOnly  |

**Response: 204 No Content**

Empty response body.

**Error Responses**

| Status | Condition       |
| ------ | --------------- |
| 401    | Not authenticated |
| 403    | Not the post owner |
| 404    | Post not found  |

---

### POST `/api/v1/social/posts/<uuid:pk>/react/`

Toggle a reaction on a post. If the user has not reacted, a reaction is created (201). If the user has already reacted with the same emoji, the reaction is removed (200). If the user reacted with a different emoji, it is updated.

| Property  | Value           |
| --------- | --------------- |
| Auth      | IsAuthenticated |

**Request Body**

| Field      | Type   | Required | Constraints                                                                |
| ---------- | ------ | -------- | -------------------------------------------------------------------------- |
| emoji_type | string | Yes      | One of: `heart`, `amen`, `praying_hands`, `fire`, and other supported types. |

**Response: 201 Created** (reaction added)

```json
{
  "message": "Reaction added.",
  "data": {
    "emoji_type": "heart"
  }
}
```

**Response: 200 OK** (reaction removed)

```json
{
  "message": "Reaction removed."
}
```

---

### GET `/api/v1/social/posts/<uuid:pk>/comments/`

List comments on a post.

| Property   | Value                              |
| ---------- | ---------------------------------- |
| Auth       | IsAuthenticated                    |
| Pagination | StandardPageNumberPagination (20/page) |

**Response: 200 OK**

```json
{
  "message": "Comments retrieved.",
  "data": {
    "count": 3,
    "next": null,
    "previous": null,
    "results": [
      {
        "id": "a7b8c9d0-e1f2-3456-abcd-567890123456",
        "user": {
          "id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
          "full_name": "John Doe",
          "profile_photo": null,
          "age": 30
        },
        "text": "Amen to this!",
        "reply_count": 1,
        "created_at": "2026-03-26T11:00:00Z",
        "updated_at": "2026-03-26T11:00:00Z"
      }
    ]
  }
}
```

---

### POST `/api/v1/social/posts/<uuid:pk>/comments/`

Add a comment to a post.

| Property  | Value           |
| --------- | --------------- |
| Auth      | IsAuthenticated |

**Request Body**

| Field | Type   | Required | Constraints         |
| ----- | ------ | -------- | ------------------- |
| text  | string | Yes      | Max 1000 characters. |

**Response: 201 Created**

Returns the Comment object.

---

### GET `/api/v1/social/posts/<uuid:pk>/share/`

Get share/deep-link data for a post.

| Property  | Value           |
| --------- | --------------- |
| Auth      | IsAuthenticated |

**Response: 200 OK**

Returns share link and metadata.

---

### GET `/api/v1/social/prayers/`

List prayers in the feed. Same pagination and structure as posts.

| Property   | Value                                |
| ---------- | ------------------------------------ |
| Auth       | IsAuthenticated                      |
| Pagination | BoostedFeedCursorPagination (cursor) |

**Query Parameters**

| Param  | Type   | Required | Description                           |
| ------ | ------ | -------- | ------------------------------------- |
| author | uuid   | No       | Filter prayers by author ID.          |
| cursor | string | No       | Cursor token for next/previous page.  |

**Response: 200 OK**

Same structure as post list but with `title` and `description` instead of `text_content`:

```json
{
  "message": "Prayers retrieved.",
  "data": {
    "next": null,
    "previous": null,
    "results": [
      {
        "id": "b8c9d0e1-f2a3-4567-bcde-678901234567",
        "author": {
          "id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
          "full_name": "John Doe",
          "profile_photo": null,
          "age": 30
        },
        "title": "Prayer for healing",
        "description": "Please join me in praying for...",
        "is_boosted": false,
        "media": [],
        "reaction_count": 25,
        "comment_count": 8,
        "user_reaction": "praying_hands",
        "created_at": "2026-03-26T09:00:00Z"
      }
    ]
  }
}
```

---

### POST `/api/v1/social/prayers/`

Create a new prayer request.

| Property  | Value           |
| --------- | --------------- |
| Auth      | IsAuthenticated |

**Request Body**

| Field       | Type           | Required | Constraints                                          |
| ----------- | -------------- | -------- | ---------------------------------------------------- |
| title       | string         | Yes      | Max 255 characters.                                  |
| description | string         | No       | Max 2000 characters.                                 |
| media_keys  | array[string]  | No       | UploadThing file keys. Max 10 items.                 |
| media_types | array[string]  | No       | Parallel array. Each value: `"image"` or `"video"`.  |
| media_files | array[file]    | No       | Direct file uploads. Max 10 items.                   |

Same media constraints as posts (max 1 video OR max 10 images).

**Response: 201 Created**

```json
{
  "message": "Prayer created.",
  "data": {
    "id": "b8c9d0e1-f2a3-4567-bcde-678901234567",
    "author": {
      "id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
      "full_name": "John Doe",
      "profile_photo": null,
      "age": 30
    },
    "title": "Prayer for healing",
    "description": "Please join me in praying for...",
    "is_boosted": false,
    "media": [],
    "reaction_count": 0,
    "comment_count": 0,
    "user_reaction": null,
    "created_at": "2026-03-26T14:45:00Z",
    "updated_at": "2026-03-26T14:45:00Z"
  }
}
```

---

### GET `/api/v1/social/prayers/<uuid:pk>/`

Retrieve a single prayer's full details.

| Property  | Value           |
| --------- | --------------- |
| Auth      | IsAuthenticated |

**Response: 200 OK**

Returns a PrayerDetail object (same shape as prayer create response).

---

### DELETE `/api/v1/social/prayers/<uuid:pk>/`

Delete a prayer. Only the prayer owner may delete it.

| Property   | Value              |
| ---------- | ------------------ |
| Auth       | IsAuthenticated    |
| Permission | IsOwnerOrReadOnly  |

**Response: 204 No Content**

---

### POST `/api/v1/social/prayers/<uuid:pk>/react/`

Toggle a reaction on a prayer. Behavior is identical to post reactions.

| Property  | Value           |
| --------- | --------------- |
| Auth      | IsAuthenticated |

**Request Body**

| Field      | Type   | Required | Constraints                           |
| ---------- | ------ | -------- | ------------------------------------- |
| emoji_type | string | Yes      | Same emoji choices as post reactions. |

**Response: 201 Created** / **200 OK**

Same behavior as post react.

---

### GET `/api/v1/social/prayers/<uuid:pk>/comments/`

List comments on a prayer.

| Property   | Value                              |
| ---------- | ---------------------------------- |
| Auth       | IsAuthenticated                    |
| Pagination | StandardPageNumberPagination (20/page) |

**Response: 200 OK**

Same Comment list structure as post comments.

---

### POST `/api/v1/social/prayers/<uuid:pk>/comments/`

Add a comment to a prayer.

| Property  | Value           |
| --------- | --------------- |
| Auth      | IsAuthenticated |

**Request Body**

| Field | Type   | Required | Constraints         |
| ----- | ------ | -------- | ------------------- |
| text  | string | Yes      | Max 1000 characters. |

**Response: 201 Created**

---

### GET `/api/v1/social/prayers/<uuid:pk>/share/`

Get share/deep-link data for a prayer.

| Property  | Value           |
| --------- | --------------- |
| Auth      | IsAuthenticated |

**Response: 200 OK**

---

### POST `/api/v1/social/comments/`

Create a comment on any commentable content type (post or prayer) using a generic relation.

| Property  | Value           |
| --------- | --------------- |
| Auth      | IsAuthenticated |

**Request Body**

| Field              | Type   | Required | Constraints                         |
| ------------------ | ------ | -------- | ----------------------------------- |
| text               | string | Yes      | Max 1000 characters.                |
| content_type_model | string | Yes      | One of: `"post"`, `"prayer"`.       |
| object_id          | uuid   | Yes      | ID of the post or prayer.           |

**Response: 201 Created**

Returns the Comment object.

---

### DELETE `/api/v1/social/comments/<uuid:pk>/`

Delete a comment. Only the comment owner may delete it.

| Property   | Value              |
| ---------- | ------------------ |
| Auth       | IsAuthenticated    |
| Permission | IsOwnerOrReadOnly  |

**Response: 204 No Content**

---

### GET `/api/v1/social/comments/<uuid:comment_pk>/replies/`

List replies to a comment.

| Property   | Value                              |
| ---------- | ---------------------------------- |
| Auth       | IsAuthenticated                    |
| Pagination | StandardPageNumberPagination (20/page) |

**Response: 200 OK**

```json
{
  "message": "Replies retrieved.",
  "data": {
    "count": 1,
    "next": null,
    "previous": null,
    "results": [
      {
        "id": "c9d0e1f2-a3b4-5678-cdef-789012345678",
        "user": {
          "id": "b2c3d4e5-f6a7-8901-bcde-f12345678901",
          "full_name": "Jane Smith",
          "profile_photo": "https://utfs.io/f/def456.jpg",
          "age": 28
        },
        "text": "I agree completely.",
        "created_at": "2026-03-26T11:30:00Z",
        "updated_at": "2026-03-26T11:30:00Z"
      }
    ]
  }
}
```

---

### POST `/api/v1/social/comments/<uuid:comment_pk>/replies/`

Add a reply to a comment.

| Property  | Value           |
| --------- | --------------- |
| Auth      | IsAuthenticated |

**Request Body**

| Field | Type   | Required | Constraints         |
| ----- | ------ | -------- | ------------------- |
| text  | string | Yes      | Max 1000 characters. |

**Response: 201 Created**

Returns the Reply object.

---

### DELETE `/api/v1/social/comments/<uuid:comment_pk>/replies/<uuid:pk>/`

Delete a reply. Only the reply owner may delete it.

| Property   | Value              |
| ---------- | ------------------ |
| Auth       | IsAuthenticated    |
| Permission | IsOwnerOrReadOnly  |

**Response: 204 No Content**

---

### POST `/api/v1/social/media/upload/`

Upload media files directly. Returns the UploadThing key and URL for use in post/prayer creation.

| Property     | Value           |
| ------------ | --------------- |
| Auth         | IsAuthenticated |
| Content-Type | multipart/form-data |

**Response: 200 OK**

```json
{
  "message": "Upload successful.",
  "data": {
    "key": "abc123def456",
    "url": "https://utfs.io/f/abc123def456.jpg",
    "type": "image"
  }
}
```

---

### POST `/api/v1/social/reports/`

Report content for moderation review.

| Property  | Value           |
| --------- | --------------- |
| Auth      | IsAuthenticated |

**Request Body**

| Field              | Type   | Required | Constraints                                                        |
| ------------------ | ------ | -------- | ------------------------------------------------------------------ |
| reason             | string | Yes      | One of: `spam`, `harassment`, `hate_speech`, `misinformation`, `other`. |
| description        | string | No       | Max 2000 characters. Additional context.                           |
| content_type_model | string | Yes      | One of: `"post"`, `"prayer"`, `"comment"`, `"user"`.               |
| object_id          | uuid   | Yes      | ID of the reported content or user.                                |

**Response: 201 Created**

```json
{
  "message": "Report submitted.",
  "data": {
    "id": "d0e1f2a3-b4c5-6789-defa-890123456789"
  }
}
```

---

## Bible

Base path: `/api/v1/bible/`

### GET `/api/v1/bible/sections/`

List all active age-segregated Bible sections.

| Property  | Value    |
| --------- | -------- |
| Auth      | AllowAny |

**Response: 200 OK**

```json
{
  "message": "Sections retrieved.",
  "data": [
    {
      "id": "11111111-1111-1111-1111-111111111111",
      "title": "Children's Bible",
      "age_min": 4,
      "age_max": 12,
      "order": 0,
      "is_active": true,
      "chapter_count": 10,
      "is_prioritized": true
    },
    {
      "id": "22222222-2222-2222-2222-222222222222",
      "title": "Youth Bible",
      "age_min": 13,
      "age_max": 17,
      "order": 1,
      "is_active": true,
      "chapter_count": 15,
      "is_prioritized": false
    }
  ]
}
```

---

### GET `/api/v1/bible/sections/<uuid>/chapters/`

List chapters within a section.

| Property  | Value    |
| --------- | -------- |
| Auth      | AllowAny |

**Response: 200 OK**

```json
{
  "message": "Chapters retrieved.",
  "data": [
    {
      "id": "33333333-3333-3333-3333-333333333333",
      "section": "11111111-1111-1111-1111-111111111111",
      "title": "Creation",
      "order": 0,
      "is_active": true,
      "page_count": 5
    }
  ]
}
```

---

### GET `/api/v1/bible/chapters/<uuid>/pages/`

List pages within a chapter.

| Property  | Value    |
| --------- | -------- |
| Auth      | AllowAny |

**Response: 200 OK**

```json
{
  "message": "Pages retrieved.",
  "data": [
    {
      "id": "44444444-4444-4444-4444-444444444444",
      "chapter": "33333333-3333-3333-3333-333333333333",
      "title": "Day 1: Light",
      "youtube_url": "https://youtube.com/watch?v=abc123",
      "order": 0,
      "is_active": true
    }
  ]
}
```

---

### GET `/api/v1/bible/pages/<uuid>/`

Retrieve full page content. Supports translation via the `lang` query parameter.

| Property  | Value    |
| --------- | -------- |
| Auth      | AllowAny |

**Query Parameters**

| Param | Type   | Required | Description                                                  |
| ----- | ------ | -------- | ------------------------------------------------------------ |
| lang  | string | No       | Language code for translation. See [Supported Languages](#supported-languages). Translated content is cached. |

**Response: 200 OK**

```json
{
  "message": "Page retrieved.",
  "data": {
    "id": "44444444-4444-4444-4444-444444444444",
    "chapter": "33333333-3333-3333-3333-333333333333",
    "title": "Day 1: Light",
    "content": "In the beginning, God created the heavens and the earth...",
    "youtube_url": "https://youtube.com/watch?v=abc123",
    "order": 0,
    "section_title": "Children's Bible",
    "chapter_title": "Creation"
  }
}
```

---

### GET `/api/v1/bible/search/`

Full-text search across Bible pages.

| Property   | Value                              |
| ---------- | ---------------------------------- |
| Auth       | AllowAny                           |
| Pagination | StandardPageNumberPagination (20/page) |

**Query Parameters**

| Param   | Type   | Required | Description                          |
| ------- | ------ | -------- | ------------------------------------ |
| q       | string | Yes      | Search query.                        |
| section | uuid   | No       | Filter results to a specific section. |

**Response: 200 OK**

Paginated list of matching pages.

---

### GET `/api/v1/bible/bookmarks/`

List the authenticated user's bookmarks.

| Property   | Value                              |
| ---------- | ---------------------------------- |
| Auth       | IsAuthenticated                    |
| Permission | IsOwner                            |
| Pagination | StandardPageNumberPagination (20/page) |

**Query Parameters**

| Param | Type   | Required | Description                                    |
| ----- | ------ | -------- | ---------------------------------------------- |
| type  | string | No       | Filter by bookmark type: `api_bible`, `segregated`. |

**Response: 200 OK**

Paginated list of bookmark objects.

---

### POST `/api/v1/bible/bookmarks/`

Create a bookmark.

| Property  | Value           |
| --------- | --------------- |
| Auth      | IsAuthenticated |

**Request Body**

| Field           | Type   | Required    | Constraints                                              |
| --------------- | ------ | ----------- | -------------------------------------------------------- |
| bookmark_type   | string | Yes         | One of: `api_bible`, `segregated`.                       |
| verse_reference | string | Conditional | Required when `bookmark_type` is `api_bible`.            |
| content_type    | int    | Conditional | Django ContentType ID. Required for `segregated` type.   |
| object_id       | uuid   | Conditional | ID of the bookmarked object. Required for `segregated` type. |

**Response: 201 Created**

---

### DELETE `/api/v1/bible/bookmarks/<uuid:pk>/`

Delete a bookmark.

| Property   | Value           |
| ---------- | --------------- |
| Auth       | IsAuthenticated |
| Permission | IsOwner         |

**Response: 204 No Content**

---

### GET `/api/v1/bible/highlights/`

List the authenticated user's highlights.

| Property   | Value                              |
| ---------- | ---------------------------------- |
| Auth       | IsAuthenticated                    |
| Permission | IsOwner                            |
| Pagination | StandardPageNumberPagination (20/page) |

**Query Parameters**

| Param | Type   | Required | Description                                       |
| ----- | ------ | -------- | ------------------------------------------------- |
| type  | string | No       | Filter by highlight type: `api_bible`, `segregated`. |

---

### POST `/api/v1/bible/highlights/`

Create a highlight.

| Property  | Value           |
| --------- | --------------- |
| Auth      | IsAuthenticated |

**Request Body**

| Field           | Type   | Required    | Constraints                                             |
| --------------- | ------ | ----------- | ------------------------------------------------------- |
| highlight_type  | string | Yes         | One of: `api_bible`, `segregated`.                      |
| color           | string | No          | One of: `yellow`, `blue`, `pink`, `green`. Default `yellow`. |
| verse_reference | string | Conditional | Required for `api_bible` type.                          |
| content_type    | int    | Conditional | Django ContentType ID. Required for `segregated` type.  |
| object_id       | uuid   | Conditional | Required for `segregated` type.                         |
| selection_start | int    | Yes         | Start position of the highlighted text.                 |
| selection_end   | int    | Yes         | End position of the highlighted text.                   |

**Response: 201 Created**

---

### DELETE `/api/v1/bible/highlights/<uuid:pk>/`

Delete a highlight.

| Property   | Value           |
| ---------- | --------------- |
| Auth       | IsAuthenticated |
| Permission | IsOwner         |

**Response: 204 No Content**

---

### GET `/api/v1/bible/notes/`

List the authenticated user's notes.

| Property   | Value                              |
| ---------- | ---------------------------------- |
| Auth       | IsAuthenticated                    |
| Permission | IsOwner                            |
| Pagination | StandardPageNumberPagination (20/page) |

**Query Parameters**

| Param | Type   | Required | Description                                  |
| ----- | ------ | -------- | -------------------------------------------- |
| type  | string | No       | Filter by note type: `api_bible`, `segregated`. |

---

### POST `/api/v1/bible/notes/`

Create a note.

| Property  | Value           |
| --------- | --------------- |
| Auth      | IsAuthenticated |

**Request Body**

| Field           | Type   | Required    | Constraints                                             |
| --------------- | ------ | ----------- | ------------------------------------------------------- |
| note_type       | string | Yes         | One of: `api_bible`, `segregated`.                      |
| text            | string | Yes         | Note content.                                           |
| verse_reference | string | Conditional | Required for `api_bible` type.                          |
| content_type    | int    | Conditional | Django ContentType ID. Required for `segregated` type.  |
| object_id       | uuid   | Conditional | Required for `segregated` type.                         |

**Response: 201 Created**

---

### PATCH `/api/v1/bible/notes/<uuid:pk>/`

Update a note's text.

| Property   | Value           |
| ---------- | --------------- |
| Auth       | IsAuthenticated |
| Permission | IsOwner         |

**Request Body**

| Field | Type   | Required | Constraints |
| ----- | ------ | -------- | ----------- |
| text  | string | Yes      |             |

**Response: 200 OK**

---

### DELETE `/api/v1/bible/notes/<uuid:pk>/`

Delete a note.

| Property   | Value           |
| ---------- | --------------- |
| Auth       | IsAuthenticated |
| Permission | IsOwner         |

**Response: 204 No Content**

---

### GET `/api/v1/bible/api-bible/`

### GET `/api/v1/bible/api-bible/<path>/`

Authenticated proxy to the API.Bible service. Forwards requests to the upstream API.Bible and returns the response.

| Property  | Value           |
| --------- | --------------- |
| Auth      | IsAuthenticated |

**Allowed Paths**

Only the following upstream path prefixes are allowed:

- `bibles` -- list and retrieve Bibles, books, chapters, verses
- `audio-bibles` -- list and retrieve audio Bible resources

All other paths will be rejected.

**Response: 200 OK**

Returns the upstream API.Bible response body.

---

## Shop

Base path: `/api/v1/shop/`

### GET `/api/v1/shop/products/`

List available products.

| Property   | Value                              |
| ---------- | ---------------------------------- |
| Auth       | IsAuthenticated                    |
| Pagination | StandardPageNumberPagination (20/page) |

**Query Parameters**

| Param    | Type   | Required | Description             |
| -------- | ------ | -------- | ----------------------- |
| category | string | No       | Filter by product category. |

**Response: 200 OK**

```json
{
  "message": "Products retrieved.",
  "data": {
    "count": 5,
    "next": null,
    "previous": null,
    "results": [
      {
        "id": "55555555-5555-5555-5555-555555555555",
        "title": "Daily Devotional eBook",
        "cover_image": "https://utfs.io/f/cover123.jpg",
        "category": "ebook",
        "is_free": false,
        "price_tier": "tier_1",
        "apple_product_id": "com.bibleway.devotional",
        "google_product_id": "devotional_ebook"
      }
    ]
  }
}
```

---

### GET `/api/v1/shop/products/<uuid:pk>/`

Retrieve full product details, including download URL if the user has access.

| Property  | Value           |
| --------- | --------------- |
| Auth      | IsAuthenticated |

**Response: 200 OK**

Full product object with `download_url` field (populated if the user has purchased or the product is free).

---

### GET `/api/v1/shop/products/search/`

Search products by title or description.

| Property   | Value                              |
| ---------- | ---------------------------------- |
| Auth       | IsAuthenticated                    |
| Pagination | StandardPageNumberPagination (20/page) |

**Query Parameters**

| Param | Type   | Required | Description   |
| ----- | ------ | -------- | ------------- |
| q     | string | Yes      | Search query. |

**Response: 200 OK**

Paginated product list.

---

### POST `/api/v1/shop/purchases/`

Record a product purchase with platform-specific receipt validation (Apple App Store or Google Play).

| Property  | Value                              |
| --------- | ---------------------------------- |
| Auth      | IsAuthenticated                    |
| Throttle  | PurchaseRateThrottle (10/min)      |

**Request Body**

| Field          | Type   | Required | Constraints                        |
| -------------- | ------ | -------- | ---------------------------------- |
| product_id     | uuid   | Yes      | ID of the product being purchased. |
| platform       | string | Yes      | One of: `ios`, `android`.          |
| receipt_data   | string | Yes      | Platform-specific receipt data.    |
| transaction_id | string | Yes      | Max 255 characters.                |

**Response: 201 Created**

```json
{
  "message": "Purchase recorded.",
  "data": {
    "id": "66666666-6666-6666-6666-666666666666",
    "product": "55555555-5555-5555-5555-555555555555",
    "platform": "ios",
    "transaction_id": "1000000123456789",
    "created_at": "2026-03-26T15:00:00Z"
  }
}
```

**Error Responses**

| Status | Condition              |
| ------ | ---------------------- |
| 400    | Invalid receipt data   |
| 401    | Not authenticated      |
| 429    | Rate limit exceeded    |

---

### GET `/api/v1/shop/purchases/list/`

List the authenticated user's purchase history.

| Property   | Value                              |
| ---------- | ---------------------------------- |
| Auth       | IsAuthenticated                    |
| Pagination | StandardPageNumberPagination (20/page) |

**Response: 200 OK**

Paginated list of Purchase objects.

---

### GET `/api/v1/shop/downloads/<uuid:product_id>/`

Generate a time-limited download URL for a product. Free products are available to any authenticated user. Paid products require a validated purchase record.

| Property  | Value           |
| --------- | --------------- |
| Auth      | IsAuthenticated |

**Response: 200 OK**

```json
{
  "message": "Download URL generated.",
  "data": {
    "download_url": "https://utfs.io/f/product-file-key?token=..."
  }
}
```

**Error Responses**

| Status | Condition                           |
| ------ | ----------------------------------- |
| 401    | Not authenticated                   |
| 403    | No valid purchase for paid product  |
| 404    | Product not found                   |

---

## Notifications

Base path: `/api/v1/notifications/`

### GET `/api/v1/notifications/`

List the authenticated user's notifications.

| Property   | Value                              |
| ---------- | ---------------------------------- |
| Auth       | IsAuthenticated                    |
| Pagination | StandardPageNumberPagination (20/page) |

**Response: 200 OK**

```json
{
  "message": "Notifications retrieved.",
  "data": {
    "count": 15,
    "next": "https://api.example.com/api/v1/notifications/?page=2",
    "previous": null,
    "results": [
      {
        "id": "77777777-7777-7777-7777-777777777777",
        "sender": {
          "id": "b2c3d4e5-f6a7-8901-bcde-f12345678901",
          "full_name": "Jane Smith",
          "profile_photo": "https://utfs.io/f/def456.jpg"
        },
        "notification_type": "follow",
        "title": "Jane Smith started following you",
        "is_read": false,
        "created_at": "2026-03-26T13:00:00Z"
      }
    ]
  }
}
```

---

### POST `/api/v1/notifications/read/`

Mark one or all notifications as read. If `notification_id` is provided, only that notification is marked. Otherwise, all unread notifications are marked as read.

| Property  | Value           |
| --------- | --------------- |
| Auth      | IsAuthenticated |

**Request Body**

| Field           | Type | Required | Constraints                              |
| --------------- | ---- | -------- | ---------------------------------------- |
| notification_id | uuid | No       | Specific notification to mark. If omitted, marks all. |

**Response: 200 OK**

```json
{
  "message": "Notifications marked as read."
}
```

---

### GET `/api/v1/notifications/unread-count/`

Get the count of unread notifications.

| Property  | Value           |
| --------- | --------------- |
| Auth      | IsAuthenticated |

**Response: 200 OK**

```json
{
  "message": "Unread count retrieved.",
  "data": {
    "count": 5
  }
}
```

---

### DELETE `/api/v1/notifications/<uuid:pk>/`

Delete a notification.

| Property  | Value           |
| --------- | --------------- |
| Auth      | IsAuthenticated |

**Response: 204 No Content**

---

### POST `/api/v1/notifications/device-tokens/`

Register a device token for push notifications (FCM).

| Property  | Value                                |
| --------- | ------------------------------------ |
| Auth      | IsAuthenticated                      |
| Throttle  | DeviceTokenRateThrottle (10/min)     |

**Request Body**

| Field    | Type   | Required | Constraints                  |
| -------- | ------ | -------- | ---------------------------- |
| token    | string | Yes      | FCM device token.            |
| platform | string | Yes      | One of: `ios`, `android`.    |

**Response: 201 Created**

```json
{
  "message": "Device token registered."
}
```

**Error Responses**

| Status | Condition           |
| ------ | ------------------- |
| 401    | Not authenticated   |
| 429    | Rate limit exceeded |

---

### POST `/api/v1/notifications/device-tokens/deregister/`

Deactivate a device token (e.g., on logout or app uninstall).

| Property  | Value           |
| --------- | --------------- |
| Auth      | IsAuthenticated |

**Request Body**

| Field | Type   | Required | Constraints       |
| ----- | ------ | -------- | ----------------- |
| token | string | Yes      | FCM device token. |

**Response: 200 OK**

```json
{
  "message": "Device token deactivated."
}
```

---

## Analytics

Base path: `/api/v1/analytics/`

### POST `/api/v1/analytics/views/`

Record a view or share event on a post or prayer.

| Property  | Value           |
| --------- | --------------- |
| Auth      | IsAuthenticated |

**Request Body**

| Field              | Type   | Required | Constraints                          |
| ------------------ | ------ | -------- | ------------------------------------ |
| content_type_model | string | Yes      | One of: `"post"`, `"prayer"`.        |
| object_id          | uuid   | Yes      | ID of the viewed content.            |
| view_type          | string | No       | One of: `"view"`, `"share"`. Default `"view"`. |

**Response: 201 Created**

```json
{
  "message": "View recorded."
}
```

---

### GET `/api/v1/analytics/posts/<uuid:post_id>/`

Retrieve analytics for a specific post.

| Property  | Value           |
| --------- | --------------- |
| Auth      | IsAuthenticated |

**Response: 200 OK**

```json
{
  "message": "Post analytics retrieved.",
  "data": {
    "views": 142,
    "reactions": 25,
    "comments": 8,
    "shares": 3
  }
}
```

---

### GET `/api/v1/analytics/me/`

Retrieve aggregate analytics for the authenticated user.

| Property  | Value           |
| --------- | --------------- |
| Auth      | IsAuthenticated |

**Response: 200 OK**

Returns aggregated metrics across all of the user's content.

---

### POST `/api/v1/analytics/boosts/`

Create a boost (paid promotion) for a post.

| Property  | Value                         |
| --------- | ----------------------------- |
| Auth      | IsAuthenticated               |
| Throttle  | BoostRateThrottle (10/min)    |

**Request Body**

| Field          | Type   | Required | Constraints                        |
| -------------- | ------ | -------- | ---------------------------------- |
| post_id        | uuid   | Yes      | ID of the post to boost.           |
| tier           | string | Yes      | Max 50 characters. Boost tier name.|
| platform       | string | Yes      | One of: `ios`, `android`.          |
| receipt_data   | string | Yes      | Platform-specific receipt data.    |
| transaction_id | string | Yes      | Max 255 characters.                |
| duration_days  | int    | Yes      | 1-365 days.                        |

**Response: 201 Created**

```json
{
  "message": "Boost created.",
  "data": {
    "id": "88888888-8888-8888-8888-888888888888",
    "post_id": "e5f6a7b8-c9d0-1234-efab-345678901234",
    "tier": "standard",
    "is_active": true,
    "start_date": "2026-03-26T15:30:00Z",
    "end_date": "2026-04-02T15:30:00Z",
    "duration_days": 7
  }
}
```

**Error Responses**

| Status | Condition           |
| ------ | ------------------- |
| 400    | Invalid receipt     |
| 401    | Not authenticated   |
| 429    | Rate limit exceeded |

---

### GET `/api/v1/analytics/boosts/list/`

List the authenticated user's boosts.

| Property   | Value                              |
| ---------- | ---------------------------------- |
| Auth       | IsAuthenticated                    |
| Pagination | StandardPageNumberPagination (20/page) |

**Query Parameters**

| Param       | Type    | Required | Description                        |
| ----------- | ------- | -------- | ---------------------------------- |
| active_only | boolean | No       | If `true`, returns only active boosts. |

**Response: 200 OK**

Paginated list of Boost objects.

---

### GET `/api/v1/analytics/boosts/<uuid:boost_id>/analytics/`

Retrieve performance analytics snapshots for a specific boost.

| Property   | Value                              |
| ---------- | ---------------------------------- |
| Auth       | IsAuthenticated                    |
| Pagination | StandardPageNumberPagination (20/page) |

**Response: 200 OK**

```json
{
  "message": "Boost analytics retrieved.",
  "data": {
    "count": 7,
    "next": null,
    "previous": null,
    "results": [
      {
        "impressions": 1500,
        "reach": 1200,
        "engagement_rate": 4.2,
        "link_clicks": 35,
        "profile_visits": 18,
        "snapshot_date": "2026-03-26"
      }
    ]
  }
}
```

---

## Verse of the Day

Base path: `/api/v1/verse-of-day/`

### GET `/api/v1/verse-of-day/today/`

Get today's verse of the day. If no scheduled verse exists for today, a random verse from the fallback pool is returned.

| Property  | Value           |
| --------- | --------------- |
| Auth      | IsAuthenticated |

**Response: 200 OK**

```json
{
  "message": "Verse of the day retrieved.",
  "data": {
    "id": "99999999-9999-9999-9999-999999999999",
    "bible_reference": "Philippians 4:13",
    "verse_text": "I can do all things through Christ who strengthens me.",
    "background_image": "https://utfs.io/f/verse-bg.jpg",
    "display_date": "2026-03-26",
    "source": "scheduled"
  }
}
```

The `source` field indicates how the verse was selected:

| Value            | Meaning                                   |
| ---------------- | ----------------------------------------- |
| `"scheduled"`    | A verse was explicitly scheduled for this date. |
| `"fallback_pool"`| No scheduled verse; picked from the fallback pool. |

---

### GET `/api/v1/verse-of-day/<str:date_str>/`

Get the verse of the day for a specific date.

| Property  | Value           |
| --------- | --------------- |
| Auth      | IsAuthenticated |

**Path Parameters**

| Param    | Type   | Format     | Description              |
| -------- | ------ | ---------- | ------------------------ |
| date_str | string | YYYY-MM-DD | The date to retrieve.    |

**Response: 200 OK**

Same structure as `today/`.

---

## Admin Panel

Base path: `/api/v1/admin/`

All admin endpoints require the user to have `is_staff=True` and an assigned `AdminRole`. Three role levels exist with different permission scopes:

| Role               | Scope                                            |
| ------------------ | ------------------------------------------------ |
| SUPER_ADMIN        | Full access to all admin endpoints.              |
| CONTENT_ADMIN      | Content management, shop, boosts, verses.        |
| MODERATION_ADMIN   | User management, reports, suspensions.           |

See [Admin Role Permissions Matrix](#admin-role-permissions-matrix) for details.

---

### Dashboard

#### GET `/api/v1/admin/dashboard/overview/`

Retrieve high-level KPI metrics.

| Property   | Value        |
| ---------- | ------------ |
| Auth       | IsAdminStaff |

**Response: 200 OK**

```json
{
  "message": "Dashboard overview.",
  "data": {
    "total_users": 15420,
    "daily_active_users": 3210,
    "new_signups_today": 47,
    "new_signups_week": 312,
    "total_posts": 8930,
    "total_prayers": 4215,
    "active_boosts_count": 23,
    "total_purchases": 890,
    "total_downloads": 1567
  }
}
```

---

#### GET `/api/v1/admin/dashboard/user-growth/`

Retrieve user growth data over a time period.

| Property   | Value        |
| ---------- | ------------ |
| Auth       | IsAdminStaff |

**Query Parameters**

| Param | Type | Required | Description                     |
| ----- | ---- | -------- | ------------------------------- |
| days  | int  | No       | Number of days. Default 30.     |

**Response: 200 OK**

```json
{
  "message": "User growth data.",
  "data": [
    { "date": "2026-02-24", "count": 42 },
    { "date": "2026-02-25", "count": 38 }
  ]
}
```

---

### User Management

#### GET `/api/v1/admin/users/`

List and search all users.

| Property   | Value                              |
| ---------- | ---------------------------------- |
| Auth       | IsModerationAdmin                  |
| Pagination | StandardPageNumberPagination (20/page) |

**Query Parameters**

| Param     | Type    | Required | Description                              |
| --------- | ------- | -------- | ---------------------------------------- |
| search    | string  | No       | Search by name or email.                 |
| country   | string  | No       | Filter by country.                       |
| is_active | boolean | No       | Filter by active status.                 |
| ordering  | string  | No       | Order by field (e.g., `date_joined`, `-date_joined`). |

---

#### GET `/api/v1/admin/users/<uuid>/`

Retrieve detailed information about a specific user including counts and admin role.

| Property | Value             |
| -------- | ----------------- |
| Auth     | IsModerationAdmin |

**Response: 200 OK**

Full user detail object with `follower_count`, `following_count`, `post_count`, `prayer_count`, and `admin_role` fields.

---

#### POST `/api/v1/admin/users/<uuid>/suspend/`

Suspend (deactivate) a user account.

| Property | Value             |
| -------- | ----------------- |
| Auth     | IsModerationAdmin |

**Request Body**

| Field  | Type   | Required | Constraints         |
| ------ | ------ | -------- | ------------------- |
| reason | string | No       | Reason for suspension. |

**Response: 200 OK**

```json
{
  "message": "User suspended."
}
```

---

#### POST `/api/v1/admin/users/<uuid>/unsuspend/`

Reactivate a suspended user account.

| Property | Value             |
| -------- | ----------------- |
| Auth     | IsModerationAdmin |

**Response: 200 OK**

```json
{
  "message": "User unsuspended."
}
```

---

### Admin User Management

#### GET `/api/v1/admin/admin-users/`

List all admin users with their roles.

| Property | Value          |
| -------- | -------------- |
| Auth     | IsSuperAdmin   |

---

#### POST `/api/v1/admin/admin-users/create/`

Create a new admin user.

| Property | Value          |
| -------- | -------------- |
| Auth     | IsSuperAdmin   |

**Request Body**

| Field         | Type   | Required | Constraints                                                     |
| ------------- | ------ | -------- | --------------------------------------------------------------- |
| email         | string | Yes      | Valid email address.                                            |
| password      | string | Yes      | See [Password Requirements](#password-requirements).             |
| full_name     | string | Yes      | Max 150 characters.                                             |
| date_of_birth | string | Yes      | Format `YYYY-MM-DD`.                                            |
| gender        | string | Yes      | One of: `male`, `female`, `prefer_not_to_say`.                  |
| role          | string | Yes      | One of: `super_admin`, `content_admin`, `moderation_admin`.     |

**Response: 201 Created**

---

#### PUT `/api/v1/admin/admin-users/<uuid>/role/`

Update an admin user's role.

| Property | Value          |
| -------- | -------------- |
| Auth     | IsSuperAdmin   |

**Request Body**

| Field | Type   | Required | Constraints                                                 |
| ----- | ------ | -------- | ----------------------------------------------------------- |
| role  | string | Yes      | One of: `super_admin`, `content_admin`, `moderation_admin`. |

**Response: 200 OK**

---

#### DELETE `/api/v1/admin/admin-users/<uuid>/delete/`

Remove admin privileges from a user (removes admin role; does not delete the user account).

| Property | Value          |
| -------- | -------------- |
| Auth     | IsSuperAdmin   |

**Response: 204 No Content**

---

### Content Moderation

#### GET `/api/v1/admin/reports/`

List reported content.

| Property   | Value                              |
| ---------- | ---------------------------------- |
| Auth       | IsModerationAdmin                  |
| Pagination | StandardPageNumberPagination (20/page) |

**Query Parameters**

| Param        | Type   | Required | Description                                   |
| ------------ | ------ | -------- | --------------------------------------------- |
| status       | string | No       | Filter by report status.                      |
| content_type | string | No       | Filter by content type (post, prayer, etc.).  |

---

#### GET `/api/v1/admin/reports/<uuid>/`

Retrieve report details including a preview of the reported content.

| Property | Value             |
| -------- | ----------------- |
| Auth     | IsModerationAdmin |

**Response: 200 OK**

Report object with `content_preview` field containing a summary of the reported content.

---

#### POST `/api/v1/admin/reports/<uuid>/action/`

Take a moderation action on a report.

| Property | Value             |
| -------- | ----------------- |
| Auth     | IsModerationAdmin |

**Request Body**

| Field           | Type   | Required | Constraints                                              |
| --------------- | ------ | -------- | -------------------------------------------------------- |
| action          | string | Yes      | One of: `dismiss`, `remove_content`, `warn`, `suspend`.  |
| warning_message | string | No       | Message to include with `warn` action.                   |

**Response: 200 OK**

---

### Verse Management

#### GET `/api/v1/admin/verses/`

List scheduled verses.

| Property   | Value                              |
| ---------- | ---------------------------------- |
| Auth       | IsContentAdmin                     |
| Pagination | StandardPageNumberPagination (20/page) |

---

#### POST `/api/v1/admin/verses/create/`

Schedule a verse of the day.

| Property     | Value           |
| ------------ | --------------- |
| Auth         | IsContentAdmin  |
| Content-Type | multipart/form-data (if uploading image) |

**Request Body**

| Field            | Type   | Required | Constraints              |
| ---------------- | ------ | -------- | ------------------------ |
| bible_reference  | string | Yes      | Max 100 characters.      |
| verse_text       | string | Yes      |                          |
| display_date     | string | Yes      | Format `YYYY-MM-DD`.     |
| background_image | file   | No       | Image file.              |

**Response: 201 Created**

---

#### PUT `/api/v1/admin/verses/<uuid>/`

Update a scheduled verse. Accepts partial fields.

| Property | Value          |
| -------- | -------------- |
| Auth     | IsContentAdmin |

---

#### DELETE `/api/v1/admin/verses/<uuid>/`

Delete a scheduled verse.

| Property | Value          |
| -------- | -------------- |
| Auth     | IsContentAdmin |

**Response: 204 No Content**

---

#### POST `/api/v1/admin/verses/bulk-create/`

Create multiple scheduled verses in a single request.

| Property | Value          |
| -------- | -------------- |
| Auth     | IsContentAdmin |

**Request Body**

| Field  | Type  | Required | Constraints                                           |
| ------ | ----- | -------- | ----------------------------------------------------- |
| verses | array | Yes      | Array of objects with `bible_reference`, `verse_text`, `display_date`. |

Example:

```json
{
  "verses": [
    {
      "bible_reference": "John 3:16",
      "verse_text": "For God so loved the world...",
      "display_date": "2026-04-01"
    },
    {
      "bible_reference": "Psalm 23:1",
      "verse_text": "The Lord is my shepherd; I shall not want.",
      "display_date": "2026-04-02"
    }
  ]
}
```

**Response: 201 Created**

---

#### GET `/api/v1/admin/verses/fallback-pool/`

List verses in the fallback pool (used when no scheduled verse exists for a date).

| Property | Value          |
| -------- | -------------- |
| Auth     | IsContentAdmin |

---

#### POST `/api/v1/admin/verses/fallback-pool/create/`

Add a verse to the fallback pool.

| Property | Value          |
| -------- | -------------- |
| Auth     | IsContentAdmin |

**Request Body**

| Field            | Type   | Required | Constraints         |
| ---------------- | ------ | -------- | ------------------- |
| bible_reference  | string | Yes      | Max 100 characters. |
| verse_text       | string | Yes      |                     |
| background_image | file   | No       | Image file.         |

**Response: 201 Created**

---

#### PUT `/api/v1/admin/verses/fallback-pool/<uuid>/`

Update a fallback pool verse.

| Property | Value          |
| -------- | -------------- |
| Auth     | IsContentAdmin |

---

#### DELETE `/api/v1/admin/verses/fallback-pool/<uuid>/`

Delete a fallback pool verse.

| Property | Value          |
| -------- | -------------- |
| Auth     | IsContentAdmin |

**Response: 204 No Content**

---

### Bible CMS

Content management endpoints for the age-segregated Bible.

#### GET `/api/v1/admin/bible/sections/`

List all Bible sections (including inactive ones).

| Property | Value          |
| -------- | -------------- |
| Auth     | IsContentAdmin |

---

#### POST `/api/v1/admin/bible/sections/`

Create a new Bible section.

| Property | Value          |
| -------- | -------------- |
| Auth     | IsContentAdmin |

**Request Body**

| Field   | Type   | Required | Constraints         |
| ------- | ------ | -------- | ------------------- |
| title   | string | Yes      | Max 255 characters. |
| age_min | int    | Yes      |                     |
| age_max | int    | Yes      |                     |
| order   | int    | No       | Default 0.          |

**Response: 201 Created**

---

#### PUT `/api/v1/admin/bible/sections/<uuid>/`

Update a Bible section.

| Property | Value          |
| -------- | -------------- |
| Auth     | IsContentAdmin |

---

#### DELETE `/api/v1/admin/bible/sections/<uuid>/`

Delete a Bible section.

| Property | Value          |
| -------- | -------------- |
| Auth     | IsContentAdmin |

**Response: 204 No Content**

---

#### GET `/api/v1/admin/bible/sections/<uuid>/chapters/`

List chapters within a section.

| Property | Value          |
| -------- | -------------- |
| Auth     | IsContentAdmin |

---

#### POST `/api/v1/admin/bible/sections/<uuid>/chapters/`

Create a new chapter within a section.

| Property | Value          |
| -------- | -------------- |
| Auth     | IsContentAdmin |

**Request Body**

| Field      | Type   | Required | Constraints         |
| ---------- | ------ | -------- | ------------------- |
| section_id | uuid   | Yes      | Parent section ID.  |
| title      | string | Yes      | Max 255 characters. |
| order      | int    | No       | Default 0.          |

**Response: 201 Created**

---

#### POST `/api/v1/admin/bible/sections/<uuid>/chapters/reorder/`

Reorder chapters within a section.

| Property | Value          |
| -------- | -------------- |
| Auth     | IsContentAdmin |

**Request Body**

| Field       | Type        | Required | Constraints                                |
| ----------- | ----------- | -------- | ------------------------------------------ |
| ordered_ids | array[uuid] | Yes      | List of chapter UUIDs in the desired order. |

**Response: 200 OK**

---

#### PUT `/api/v1/admin/bible/chapters/<uuid>/`

Update a chapter.

| Property | Value          |
| -------- | -------------- |
| Auth     | IsContentAdmin |

---

#### DELETE `/api/v1/admin/bible/chapters/<uuid>/`

Delete a chapter.

| Property | Value          |
| -------- | -------------- |
| Auth     | IsContentAdmin |

**Response: 204 No Content**

---

#### GET `/api/v1/admin/bible/chapters/<uuid>/pages/`

List pages within a chapter.

| Property | Value          |
| -------- | -------------- |
| Auth     | IsContentAdmin |

---

#### POST `/api/v1/admin/bible/chapters/<uuid>/pages/`

Create a new page within a chapter.

| Property | Value          |
| -------- | -------------- |
| Auth     | IsContentAdmin |

**Request Body**

| Field       | Type   | Required | Constraints                  |
| ----------- | ------ | -------- | ---------------------------- |
| chapter_id  | uuid   | Yes      | Parent chapter ID.           |
| title       | string | Yes      | Max 255 characters.          |
| content     | string | Yes      | Page body content.           |
| youtube_url | string | No       | Valid URL.                   |
| order       | int    | No       | Default 0.                   |

**Response: 201 Created**

---

#### GET `/api/v1/admin/bible/pages/<uuid>/`

Retrieve a page's full details.

| Property | Value          |
| -------- | -------------- |
| Auth     | IsContentAdmin |

---

#### PUT `/api/v1/admin/bible/pages/<uuid>/`

Update a page.

| Property | Value          |
| -------- | -------------- |
| Auth     | IsContentAdmin |

---

#### DELETE `/api/v1/admin/bible/pages/<uuid>/`

Delete a page.

| Property | Value          |
| -------- | -------------- |
| Auth     | IsContentAdmin |

**Response: 204 No Content**

---

### Shop Management

#### GET `/api/v1/admin/shop/products/`

List all products (including inactive ones).

| Property   | Value                              |
| ---------- | ---------------------------------- |
| Auth       | IsContentAdmin                     |
| Pagination | StandardPageNumberPagination (20/page) |

**Query Parameters**

| Param     | Type    | Required | Description               |
| --------- | ------- | -------- | ------------------------- |
| category  | string  | No       | Filter by category.       |
| is_active | boolean | No       | Filter by active status.  |

---

#### POST `/api/v1/admin/shop/products/`

Create a new product.

| Property     | Value           |
| ------------ | --------------- |
| Auth         | IsContentAdmin  |
| Content-Type | multipart/form-data |

**Request Body**

| Field             | Type    | Required | Constraints                     |
| ----------------- | ------- | -------- | ------------------------------- |
| title             | string  | Yes      |                                 |
| description       | string  | Yes      |                                 |
| cover_image       | file    | Yes      | Image file.                     |
| product_file      | file    | Yes      | Downloadable product file.      |
| category          | string  | Yes      | Product category.               |
| is_free           | boolean | No       | Default false.                  |
| price_tier        | string  | No       | Pricing tier identifier.        |
| apple_product_id  | string  | No       | Apple App Store product ID.     |
| google_product_id | string  | No       | Google Play product ID.         |

**Response: 201 Created**

---

#### GET `/api/v1/admin/shop/products/<uuid>/`

Retrieve full product details.

| Property | Value          |
| -------- | -------------- |
| Auth     | IsContentAdmin |

---

#### PUT `/api/v1/admin/shop/products/<uuid>/`

Update a product.

| Property | Value          |
| -------- | -------------- |
| Auth     | IsContentAdmin |

---

#### DELETE `/api/v1/admin/shop/products/<uuid>/`

Delete a product.

| Property | Value          |
| -------- | -------------- |
| Auth     | IsContentAdmin |

**Response: 204 No Content**

---

#### POST `/api/v1/admin/shop/products/<uuid>/toggle-active/`

Toggle a product's active status.

| Property | Value          |
| -------- | -------------- |
| Auth     | IsContentAdmin |

**Response: 200 OK**

---

#### GET `/api/v1/admin/shop/products/<uuid>/stats/`

Retrieve sales statistics for a product.

| Property | Value          |
| -------- | -------------- |
| Auth     | IsContentAdmin |

**Response: 200 OK**

```json
{
  "message": "Product stats.",
  "data": {
    "purchase_count": 142,
    "download_count": 98
  }
}
```

---

#### GET `/api/v1/admin/shop/purchases/`

List all purchases with optional filters.

| Property   | Value                              |
| ---------- | ---------------------------------- |
| Auth       | IsContentAdmin                     |
| Pagination | StandardPageNumberPagination (20/page) |

**Query Parameters**

| Param      | Type | Required | Description                |
| ---------- | ---- | -------- | -------------------------- |
| product_id | uuid | No       | Filter by product.         |
| user_id    | uuid | No       | Filter by purchasing user. |

---

### Boost Management

#### GET `/api/v1/admin/boosts/`

List all boosts.

| Property   | Value                              |
| ---------- | ---------------------------------- |
| Auth       | IsContentAdmin                     |
| Pagination | StandardPageNumberPagination (20/page) |

**Query Parameters**

| Param     | Type    | Required | Description                    |
| --------- | ------- | -------- | ------------------------------ |
| is_active | boolean | No       | Filter by active status.       |
| user_id   | uuid    | No       | Filter by boost owner.         |

---

#### GET `/api/v1/admin/boosts/<uuid>/`

Retrieve boost details including snapshots.

| Property | Value          |
| -------- | -------------- |
| Auth     | IsContentAdmin |

---

#### GET `/api/v1/admin/boosts/tiers/`

List all boost tiers.

| Property | Value          |
| -------- | -------------- |
| Auth     | IsContentAdmin |

---

#### POST `/api/v1/admin/boosts/tiers/`

Create a new boost tier.

| Property | Value          |
| -------- | -------------- |
| Auth     | IsContentAdmin |

**Request Body**

| Field             | Type   | Required | Constraints                 |
| ----------------- | ------ | -------- | --------------------------- |
| name              | string | Yes      |                             |
| apple_product_id  | string | Yes      | Apple App Store product ID. |
| google_product_id | string | Yes      | Google Play product ID.     |
| duration_days     | int    | Yes      |                             |
| display_price     | string | Yes      | Human-readable price string.|

**Response: 201 Created**

---

#### PUT `/api/v1/admin/boosts/tiers/<uuid>/`

Update a boost tier.

| Property | Value          |
| -------- | -------------- |
| Auth     | IsContentAdmin |

---

#### DELETE `/api/v1/admin/boosts/tiers/<uuid>/`

Delete a boost tier.

| Property | Value          |
| -------- | -------------- |
| Auth     | IsContentAdmin |

**Response: 204 No Content**

---

#### GET `/api/v1/admin/boosts/revenue/`

Retrieve boost revenue summary.

| Property | Value          |
| -------- | -------------- |
| Auth     | IsContentAdmin |

**Response: 200 OK**

```json
{
  "message": "Boost revenue.",
  "data": {
    "total_boosts": 156,
    "active_boosts": 23,
    "revenue_by_tier": {
      "standard": 45,
      "premium": 12
    }
  }
}
```

---

### Broadcasts

#### GET `/api/v1/admin/broadcasts/`

List all broadcast notifications.

| Property | Value        |
| -------- | ------------ |
| Auth     | IsAdminStaff |

---

#### POST `/api/v1/admin/broadcasts/create/`

Create and send a broadcast push notification.

| Property | Value        |
| -------- | ------------ |
| Auth     | IsAdminStaff |

**Request Body**

| Field   | Type   | Required | Constraints                                                                  |
| ------- | ------ | -------- | ---------------------------------------------------------------------------- |
| title   | string | Yes      | Max 255 characters.                                                          |
| body    | string | Yes      | Notification body text.                                                      |
| filters | object | No       | Targeting filters. See below.                                                |

**Filters Object**

| Field    | Type   | Description                        |
| -------- | ------ | ---------------------------------- |
| country  | string | Target users in this country.      |
| language | string | Target users with this language.   |
| gender   | string | Target users of this gender.       |
| age_min  | int    | Minimum age for targeting.         |
| age_max  | int    | Maximum age for targeting.         |

Example:

```json
{
  "title": "Sunday Service Reminder",
  "body": "Join us for worship this Sunday!",
  "filters": {
    "country": "United States",
    "language": "en",
    "age_min": 18
  }
}
```

**Response: 201 Created**

---

#### GET `/api/v1/admin/broadcasts/<uuid>/`

Retrieve broadcast details including recipient count.

| Property | Value        |
| -------- | ------------ |
| Auth     | IsAdminStaff |

**Response: 200 OK**

Broadcast object with `recipient_count` field.

---

### Admin Analytics

#### GET `/api/v1/admin/analytics/demographics/`

Retrieve user demographic breakdowns.

| Property | Value        |
| -------- | ------------ |
| Auth     | IsAdminStaff |

**Response: 200 OK**

```json
{
  "message": "Demographics data.",
  "data": {
    "age_distribution": {
      "13-17": 320,
      "18-24": 4500,
      "25-34": 6200,
      "35-44": 2800,
      "45+": 1600
    },
    "gender_split": {
      "male": 7200,
      "female": 7500,
      "prefer_not_to_say": 720
    },
    "top_countries": [
      { "country": "United States", "count": 5200 },
      { "country": "Nigeria", "count": 3100 },
      { "country": "Kenya", "count": 1800 }
    ],
    "language_distribution": {
      "en": 9800,
      "es": 2100,
      "sw": 1500,
      "fr": 980
    }
  }
}
```

---

#### GET `/api/v1/admin/analytics/content-engagement/`

Retrieve content engagement metrics over time.

| Property | Value        |
| -------- | ------------ |
| Auth     | IsAdminStaff |

**Query Parameters**

| Param | Type | Required | Description                 |
| ----- | ---- | -------- | --------------------------- |
| days  | int  | No       | Number of days. Default 30. |

**Response: 200 OK**

```json
{
  "message": "Content engagement data.",
  "data": [
    {
      "date": "2026-03-25",
      "posts": 42,
      "prayers": 18,
      "reactions": 320,
      "comments": 87
    }
  ]
}
```

---

#### GET `/api/v1/admin/analytics/shop-revenue/`

Retrieve shop revenue analytics.

| Property | Value        |
| -------- | ------------ |
| Auth     | IsAdminStaff |

**Query Parameters**

| Param | Type | Required | Description                 |
| ----- | ---- | -------- | --------------------------- |
| days  | int  | No       | Number of days. Default 30. |

**Response: 200 OK**

```json
{
  "message": "Shop revenue data.",
  "data": [
    {
      "date": "2026-03-25",
      "purchase_count": 12,
      "product_breakdown": {
        "ebook": 8,
        "audiobook": 4
      }
    }
  ]
}
```

---

#### GET `/api/v1/admin/analytics/boost-performance/`

Retrieve aggregate boost performance metrics.

| Property | Value        |
| -------- | ------------ |
| Auth     | IsAdminStaff |

**Response: 200 OK**

Returns aggregate boost performance data.

---

### Admin Logs

#### GET `/api/v1/admin/logs/`

Retrieve the admin audit trail. All admin actions are logged automatically.

| Property   | Value                              |
| ---------- | ---------------------------------- |
| Auth       | IsSuperAdmin                       |
| Pagination | StandardPageNumberPagination (20/page) |

**Query Parameters**

| Param         | Type   | Required | Description                        |
| ------------- | ------ | -------- | ---------------------------------- |
| admin_user_id | uuid   | No       | Filter by the admin who performed the action. |
| action        | string | No       | Filter by action type.             |
| target_model  | string | No       | Filter by target model name.       |

**Response: 200 OK**

```json
{
  "message": "Admin logs.",
  "data": {
    "count": 245,
    "next": "https://api.example.com/api/v1/admin/logs/?page=2",
    "previous": null,
    "results": [
      {
        "id": "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa",
        "admin_user": {
          "id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
          "full_name": "Admin User",
          "email": "admin@bibleway.com"
        },
        "action": "suspend_user",
        "target_model": "CustomUser",
        "target_id": "b2c3d4e5-f6a7-8901-bcde-f12345678901",
        "detail": "User suspended for TOS violation.",
        "metadata": {},
        "created_at": "2026-03-26T16:00:00Z"
      }
    ]
  }
}
```

---

## Health Check

### GET `/api/v1/health/`

Basic health check endpoint that verifies the API and database are operational.

| Property  | Value    |
| --------- | -------- |
| Auth      | AllowAny |

**Response: 200 OK**

```json
{
  "status": "ok",
  "db": "ok"
}
```

---

## Reference

### Password Requirements

All password fields (registration, password reset, password change) enforce the following rules:

| Rule                         | Constraint                                          |
| ---------------------------- | --------------------------------------------------- |
| Minimum length               | 8 characters                                        |
| Maximum length               | 128 characters                                      |
| Uppercase letter             | At least 1 required                                 |
| Lowercase letter             | At least 1 required                                 |
| Digit                        | At least 1 required                                 |
| Special character            | At least 1 required                                 |
| Common password check        | Django's built-in common password validator applies  |
| Similarity to user attributes| Must not be too similar to email or full name        |

---

### Supported Languages

The following language codes are accepted for `preferred_language` and the `?lang=` translation parameter:

| Code | Language    |
| ---- | ----------- |
| ar   | Arabic      |
| de   | German      |
| en   | English     |
| es   | Spanish     |
| fr   | French      |
| hi   | Hindi       |
| it   | Italian     |
| ja   | Japanese    |
| ko   | Korean      |
| pt   | Portuguese  |
| ru   | Russian     |
| sw   | Swahili     |
| zh   | Chinese     |

---

### Rate Limits

| Scope         | Limit   | Applies To                                               |
| ------------- | ------- | -------------------------------------------------------- |
| auth          | 10/min  | `register/`, `login/`                                    |
| otp           | 5/min   | `verify-email/`, `auth/resend-otp/`, `password-reset/`, `password-reset/confirm/` |
| purchase      | 10/min  | `POST /shop/purchases/`                                  |
| boost         | 10/min  | `POST /analytics/boosts/`                                |
| device_token  | 10/min  | `POST /notifications/device-tokens/`                     |

When a rate limit is exceeded, the API returns:

```
HTTP 429 Too Many Requests
```

```json
{
  "message": "Request was throttled. Expected available in X seconds."
}
```

---

### Pagination Formats

#### Standard Page Number Pagination

Used by most list endpoints. Page size is 20 items per page.

**Query Parameters**

| Param | Type | Description           |
| ----- | ---- | --------------------- |
| page  | int  | Page number (1-based).|

**Response Shape**

```json
{
  "count": 100,
  "next": "https://api.example.com/api/v1/resource/?page=3",
  "previous": "https://api.example.com/api/v1/resource/?page=1",
  "results": [ ]
}
```

| Field    | Type        | Description                                |
| -------- | ----------- | ------------------------------------------ |
| count    | int         | Total number of items across all pages.    |
| next     | string/null | URL for the next page, or null if last.    |
| previous | string/null | URL for the previous page, or null if first.|
| results  | array       | Array of items for the current page.       |

#### Cursor Pagination (Feed)

Used by feed endpoints (`posts/`, `prayers/`). Provides stable, efficient pagination for infinite-scroll UIs. Uses the `BoostedFeedCursorPagination` class, which also intersperses boosted content.

**Query Parameters**

| Param  | Type   | Description                   |
| ------ | ------ | ----------------------------- |
| cursor | string | Opaque cursor token.          |

**Response Shape**

```json
{
  "next": "https://api.example.com/api/v1/social/posts/?cursor=cD0yMDI2...",
  "previous": null,
  "results": [ ]
}
```

| Field    | Type        | Description                                    |
| -------- | ----------- | ---------------------------------------------- |
| next     | string/null | URL with cursor for the next page.             |
| previous | string/null | URL with cursor for the previous page.         |
| results  | array       | Array of items for the current page.           |

Note: Cursor pagination does not provide a `count` field.

---

### HTTP Status Codes

| Code | Meaning               | Usage                                                                 |
| ---- | --------------------- | --------------------------------------------------------------------- |
| 200  | OK                    | Successful retrieval, update, or action.                              |
| 201  | Created               | Resource successfully created (registration, post, comment, etc.).    |
| 204  | No Content            | Successful deletion. Response body is empty.                          |
| 400  | Bad Request           | Validation errors, invalid input, weak password, wrong credentials.   |
| 401  | Unauthorized          | Missing, invalid, or expired access token.                            |
| 403  | Forbidden             | Insufficient permissions (not owner, blocked, wrong admin role).      |
| 404  | Not Found             | Resource does not exist or is not accessible.                         |
| 409  | Conflict              | Duplicate action (email exists, already following, already blocked).  |
| 429  | Too Many Requests     | Rate limit exceeded. Retry after the indicated time.                  |

---

### Authentication Flow

The full authentication lifecycle for a new user:

```
1. Register
   POST /api/v1/accounts/register/
   --> Account created (is_email_verified = false)
   --> 6-digit OTP sent to email

2. Verify Email
   POST /api/v1/accounts/verify-email/
   --> Email verified (is_email_verified = true)
   --> Account is now fully active

   (If OTP expired or not received)
   POST /api/v1/accounts/auth/resend-otp/
   --> New OTP sent

3. Login
   POST /api/v1/accounts/login/
   --> Returns access token (15min) + refresh token (30d)

4. Use Access Token
   All authenticated requests include:
   Authorization: Bearer <access_token>

5. Refresh Token (before access expires)
   POST /api/v1/accounts/token/refresh/
   --> Returns new access + new refresh (old refresh is blacklisted)

6. Logout
   POST /api/v1/accounts/logout/
   --> Refresh token blacklisted

Password Reset Flow:
   POST /api/v1/accounts/password-reset/        --> OTP sent
   POST /api/v1/accounts/password-reset/confirm/ --> Password changed, all sessions invalidated
```

---

### Admin Role Permissions Matrix

Three admin role levels control access to admin panel endpoints. All admin users must have `is_staff=True` in addition to their assigned role.

| Endpoint Group         | SUPER_ADMIN | CONTENT_ADMIN | MODERATION_ADMIN |
| ---------------------- | :---------: | :-----------: | :--------------: |
| Dashboard              | Yes         | Yes           | Yes              |
| User Management        | Yes         | No            | Yes              |
| Admin User Management  | Yes         | No            | No               |
| Content Moderation     | Yes         | No            | Yes              |
| Verse Management       | Yes         | Yes           | No               |
| Bible CMS              | Yes         | Yes           | No               |
| Shop Management        | Yes         | Yes           | No               |
| Boost Management       | Yes         | Yes           | No               |
| Broadcasts             | Yes         | Yes           | Yes              |
| Admin Analytics        | Yes         | Yes           | Yes              |
| Admin Logs             | Yes         | No            | No               |
