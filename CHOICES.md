# Test choice

A recorded wake prints REJECTED. It does not print NOT COVERED. A gap prints NOT COVERED, and a wake stays a different result.

The closing page finishes at the claim deadline, as the same time text. A page that finishes earlier, or a page that runs past the deadline, is NOT COVERED.

The next page starts where the previous page stopped: its cursor equals the previous page bound. A cursor that does not match is NOT COVERED.

A returned id counts only when it is a whole number from the page cursor up to, and not including, the page bound. An id outside that page, including a target listed after a later cursor, is NOT COVERED.

A page whose bound is smaller than its cursor is NOT COVERED, even when that page lists no ids. A bound equal to its cursor is still allowed.

A whole-number time sorts as that number. The text "20" is after "3". A close earlier than the page it continues is NOT COVERED. Every time in one claim must be the same kind.

A clock time with a zone compares as that instant. Zulu and an offset are the same kind. A time with no zone is NOT COVERED. The closing page still matches the deadline as the same text.

Kiln wrote the checker. Sift set the contract. Beacon wrote the public wording. Probe checked that wording. Flint reviewed the release.
