# Implementation notes: Issues #18 and #23

## Issue #18: Profile and account settings
- Added authenticated `PATCH /api/auth/profile` for updating the current user's full name and email.
- Email addresses are normalized to lowercase, validated, length-limited, and checked for uniqueness.
- Profile changes are restricted to the authenticated session; callers cannot select another user's ID.
- Added authenticated `PATCH /api/auth/password` requiring the current password, applying the existing password policy, and rejecting reuse of the same password.
- Passwords continue to be stored using the application's existing bcrypt hashing helper.
- Added audit events for successful profile updates, successful password changes, and failed password verification.
- Added a protected React profile/settings page and navigation link for all signed-in roles.

## Issue #23: UI and accessibility
- Added visible keyboard focus styling for interactive controls.
- Added reduced-motion support for users who request reduced motion.
- Improved the navigation layout at tablet/mobile breakpoints and profile settings layout at narrow widths.
- Profile forms have explicit labels, autocomplete hints, accessible status/error announcements, and password guidance.

## Tests
`backend/tests/test_profile_settings.py` adds integration coverage for authentication, CSRF protection, valid profile updates, duplicate/invalid emails, password verification and policy, successful password change/re-login, and isolation from other users' records.
