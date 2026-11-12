# Submission notes

## Runtime and entry point

`solution.py` exposes `build()`, returning `ingest`, `answer`, and `conflicts`
methods compatible with the unchanged participant contract. The canonical
submission is the repository's root `submission/` directory. The solution uses
only Python's standard library and requires no API keys or network calls.
Validation targets Python 3.11.

## Choosing a snapshot and matching a product

Each crawl has a separate in-memory index. An explicit `as_of` argument or a
recognized date in the question selects the latest crawl on or before that date.
Questions before the earliest crawl abstain. This is observation-time snapshot
selection, not a general model of every fact's real-world validity interval.
Calendar dates are validated without a fixed year whitelist. Date text is removed
before product matching, so a date such as `7/1/2026` cannot be mistaken for an ARM.
Invalid dates abstain, and a month-only date includes that month's actual last day.
Abbreviated months are accepted; year-only anchors use year end. Unrecognized
explicit `as of` requests abstain instead of defaulting to current data.

Tables retain their headers and rows. Certificate records distinguish personal
and business products, term, jumbo status, special/fixed/flex status, and minimum
deposit. Mortgage records retain term, purchase/refinance purpose, amount tier,
interest rate, and APR. A requested amount selects the smallest published tier
that covers it without changing the requested term. Broad requests list the
applicable conditions instead of silently substituting a different product.
Mortgage program and fixed/adjustable qualifiers must also match; an absent FHA,
VA, or ARM schedule cannot borrow a conventional fixed rate. Dollar symbols,
currency words, and amount suffixes share the same amount parser. Negated jumbo
requests match non-jumbo certificates.
Commercial/business and payment-structure qualifiers such as interest-only,
balloon, and reverse also require a matching published program. Signed balances
retain their signs; negative balances cannot match positive deposit tiers, and
nonpositive mortgage amounts abstain.
Flex/fixed certificate qualifiers are also retained for specific terms and broad
lists. An unavailable flex product cannot inherit a fixed-certificate rate.

Numeric and spelled-out terms share a parser. Compound expressions are matched
as whole numbers, so “thirty-six months” and “36 months” select the same term.
Decimal years convert to whole months (for example, 1.5 years is 18 months).
Invalid, nonpositive, malformed, or fractional-month terms abstain rather than
matching a numeric suffix or becoming an unrestricted product request.

## Source precedence and answers

Dedicated product schedules rank above secondary pages, calculators, and legacy
copies. Certificate entries are resolved by product/tier before formatting:
lower-authority conflicting rates are omitted from the answer, the winning page
is cited, and a conflict note explains the choice. Equally authoritative
disagreement causes an explicit refusal rather than a guessed winner.

Auto-loan summaries and minimum rates are calculated from the selected official
table with the applicable model years and term. Mortgage answers use the selected
table and preserve the requested term and purpose. Personal-loan queries stay
within the personal-loan schedule and abstain on unpublished terms.
Shared question parsing normalizes product spellings such as `personal-loan`.
An explicit personal-loan request takes precedence over purchase-purpose words
such as car or motorcycle.
Mortgage, auto, and personal-loan answers resolve duplicate records before
formatting or choosing a minimum rate. Equal-authority disagreements abstain,
including overlapping vehicle-year cohorts. Selecting a mortgage amount tier
preserves every source at that tier for resolution; page order cannot choose a
winner. APR column headings identify the metric even when cells omit “APR”.
Explicit four-digit vehicle years are matched without a 2029 cutoff, and money
amounts are removed before model-year extraction. An unpublished year abstains.

Credit-card APRs are extracted from the selected snapshot's tables and disclosures,
with personal/business and Platinum/Rewards identities kept separate. Standard
purchase answers exclude introductory rates. Checking APYs come from observed
account and balance rows, accepting both `Balance` and `Balance Tier` headers.
Answers and conflict resolutions use the same checking records and authority
rules; changing an official APY changes both outputs. Missing records or equally
authoritative disagreements cause an explicit refusal.
Savings use observed account and balance rows as well: amounts such as `$110,000`
and `$100k` are compared numerically. Deposit answers preserve APY versus dividend
rate, and unknown named accounts cannot become generic account lists. Requests
for unindexed account attributes abstain rather than receiving an unrelated rate.

Card annual fees, cash-advance fees, and introductory APRs/durations are indexed
separately from standard purchase APRs. Each detail retains the disclosure's card
identity and source excerpt. Personal, business, and requests for both families
have distinct selection behavior. Missing details and equal-authority fee
disagreements abstain.
Unknown card names and unsupported networks cannot inherit another card's APR.
Multiple requested card attributes are retained, with a source for each detail;
if any requested detail is missing or unresolved, the answer abstains. A standard
APR requested after an introductory offer remains distinct from asking for both.

Specific branch-hours queries require a schedule associated with that branch's
article or heading. An unknown branch cannot inherit a generic schedule. General
hours questions still receive the supplied website's general overview. The
directory is incomplete, so absence from it is not proof that a branch does not
exist. Address aliases and announcements are handled separately from hours.
Address matching requires complete distinguishing words, so an unknown Churchill
branch cannot match Flint Hill through the substring “hill”.
Bare questions such as “Churchill lobby hours?” also retain the branch name;
general hours remain available for explicitly general requests.
Address requests retain both branch name and city. A city match cannot override
an unknown branch name, and a named branch must match the requested city. Existing
address aliases use the same matching rules as directory entries.

## Conflict reporting

Conflicts are constructed from observed financial records, not a preset list of
answers or snapshot identifiers. A comparison key includes the product and its
qualifiers. Mortgage rate and APR, different balance bands, and personal versus
business products are kept separate. Identical values with different numeric
formatting are not conflicts.

Each reported value carries a source URL, its actual snapshot ID, and a supporting
row or excerpt. The newest observed snapshot governs current values; within that
snapshot, source authority selects the winner. Equal-authority disagreement is
reported with no resolution. Older values keep their original citations.
Overlapping auto-loan year cohorts are compared at shared years and compacted
when their evidence is identical. Compact prose certificate schedules, including
the provided self-test, use the same observed-value comparison.
Their answers also use exact parsed terms: an unpublished thirty-six-month product
cannot match the text of a six-month product.

The implemented conflict extractors cover certificate APYs, auto and personal-loan APRs, mortgage
rates/APRs, and checking APYs by balance tier. They do not claim exhaustive
contradiction detection for arbitrary prose, navigation links, or institutional
statistics. The former unsupported fixed nonfinancial catalog was removed.

## Other coverage and limits

Some institutional, fee, and navigation answers remain curated rules for this
supplied corpus. General queries use authority-weighted BM25 retrieval with
conservative filtering. This is not a claim that arbitrary future websites,
unseen table formats, every paraphrase, or every temporal expression are covered.
Unsupported questions and unresolved comparisons should abstain.

The regression suite tests concrete failures and input changes. Repeated calls
are deterministic, but determinism alone does not prove paraphrase correctness.
The public suite's singleton paraphrase groups do not provide that evidence.

## Evaluation and data handling

The official harness and evaluations are unchanged. The public free-text item
`dup-005` needs the optional semantic judge; without it, even its reference answer
scores zero. Public results and the one-conflict synthetic self-test cannot
certify the hidden score or full-dataset conflict precision/recall.

Real website snapshots, downloaded archives, bytecode, and generated results are
excluded from Git. The small synthetic self-test fixtures are included. The root
README gives clean-checkout commands with the authorized dataset supplied
externally. There are no external dependencies in `requirements.txt`.
