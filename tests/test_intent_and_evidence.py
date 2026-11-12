"""Regression coverage for account identity, metrics, dates, and card attributes."""
import unittest

from test_regressions import AUTO, PERSONAL, build, certs, page, snapshot
from test_product_correctness import CHECKING, PERSONAL_CARD, BUSINESS_CARD, PERSONAL_LOAN, checking


def savings(high='0.20%'):
    return f'''# Savings rates
| Account Type | Balance Tier | Dividend Rate | APY |
| --- | --- | --- | --- |
| Share Savings | $25,000+ | {high} | {high} |
| Share Savings | $10,000 - $24,999.99 | 0.15% | 0.15% |
| Share Savings | $100 - $9,999.99 | 0.10% | 0.10% |
| Launchpad Savings | $5 - $1,000 | 3.21% | 3.25% |
| Bright Savings | $0.01 - $1,000,000 | 2.23% | 2.25% |
'''


class DepositIntentTests(unittest.TestCase):
    def setUp(self):
        self.system = build(snapshot(page(PERSONAL, savings()), page(CHECKING, checking())))

    def test_large_balance_spellings_keep_account_and_tier(self):
        for amount in ('$110,000', '$210,000', '$100k', '100000 dollars', 'USD 100000', '100,000'):
            with self.subTest(amount=amount):
                answer = self.system.answer(f'What is the Share Savings APY for a balance of {amount}?')
                self.assertTrue(answer.confident)
                self.assertIn('0.20%', answer.text)
                self.assertNotIn('0.15%', answer.text)
                self.assertNotIn('Launchpad', answer.text)
                self.assertEqual({s.url for s in answer.sources}, {PERSONAL})
                self.assertTrue(all('Share Savings' in s.quote for s in answer.sources))

    def test_savings_balance_boundary_uses_numeric_comparison(self):
        for amount, rate in [('9,999.99', '0.10%'), ('10,000', '0.15%'),
                             ('24,999.99', '0.15%'), ('25,000', '0.20%')]:
            answer = self.system.answer(f'Share Savings APY with ${amount}?')
            self.assertTrue(answer.confident)
            self.assertIn(rate, answer.text)
            self.assertEqual(len(answer.sources), 1)

    def test_savings_answers_track_updated_and_historical_data(self):
        self.system.ingest(snapshot(page(PERSONAL, savings('0.45%')), name='later', date='2026-08-01'))
        self.assertIn('0.45%', self.system.answer('Share Savings APY for $110k?').text)
        self.assertIn('0.20%', self.system.answer('Share Savings APY for $110k?', '2026-06-01').text)

    def test_highest_uses_the_requested_savings_account(self):
        answer = self.system.answer('What is the highest Share Savings APY?')
        self.assertIn('0.20%', answer.text)
        self.assertNotIn('3.25%', answer.text)
        self.assertIn('$25,000+', answer.text)

    def test_dividend_and_apy_are_distinct_requested_metrics(self):
        for product, dividend, apy in [('1st Rate Checking', '2.72%', '2.75%'),
                                       ('Bright Savings', '2.23%', '2.25%')]:
            with self.subTest(product=product):
                dividend_answer = self.system.answer(f'{product} dividend rate for $10k?')
                apy_answer = self.system.answer(f'{product} APY for $10k?')
                both = self.system.answer(f'{product} dividend rate and APY for $10k?')
                self.assertIn(dividend, dividend_answer.text)
                self.assertNotIn(apy, dividend_answer.text)
                self.assertIn(apy, apy_answer.text)
                self.assertNotIn(dividend, apy_answer.text)
                self.assertIn(dividend, both.text)
                self.assertIn(apy, both.text)

    def test_dividend_disagreement_cannot_be_hidden_by_matching_apy(self):
        system = build(snapshot(page(CHECKING, checking()),
                                page(CHECKING + '/', checking().replace('2.72%', '2.60%'))))
        self.assertFalse(system.answer('1st Rate Checking dividend rate for $10k?').confident)
        self.assertTrue(system.answer('1st Rate Checking APY for $10k?').confident)

    def test_unknown_named_account_does_not_become_a_generic_list(self):
        for name in ('Premier', 'Atlantis', 'Premier Free'):
            for family in ('Checking', 'Savings'):
                with self.subTest(name=name, family=family):
                    self.assertFalse(self.system.answer(f'What is the APY on {name} {family} for $10k?').confident)

    def test_new_published_account_is_matched_from_source(self):
        md = checking().replace('1st Rate Checking', 'Premier Checking')
        system = build(snapshot(page(CHECKING, md)))
        answer = system.answer('Premier Checking APY for $10k?')
        self.assertTrue(answer.confident)
        self.assertIn('2.75%', answer.text)
        self.assertTrue(all('Premier Checking' in s.quote for s in answer.sources))

    def test_generic_account_requests_still_work(self):
        for q in ('Provide current checking account interest rates', 'List checking account APYs',
                  "What's the checking APY?", 'What savings account options do you offer?'):
            with self.subTest(q=q):
                self.assertTrue(self.system.answer(q).confident)

    def test_non_rate_account_question_does_not_receive_an_apy(self):
        for q in ('What is the monthly fee on 1st Rate Checking?',
                  'How do I open a Share Savings account?'):
            answer = self.system.answer(q)
            self.assertFalse(answer.confident)
            self.assertNotIn('0.20%', answer.text)
            self.assertNotIn('2.75%', answer.text)


class LoanAndCertificateIntentTests(unittest.TestCase):
    def setUp(self):
        personal = '''| Term | APR |
| --- | --- |
| 36 Months | 10.49% APR |
| 60 Months | 12.49% APR |
'''
        auto = '''| Model Year | Term | APR |
| --- | --- | --- |
| 2021-23 Model Year | 60 Months | 5.64% APR |
| 2024-27 Model Year | 72 Months | 5.49% APR |
'''
        self.system = build(snapshot(page(PERSONAL_LOAN, personal), page(AUTO, auto)))

    def test_personal_loan_spelling_does_not_change_identity(self):
        for product in ('personal loan', 'personal-loan', 'personal–loan', 'personal loans'):
            with self.subTest(product=product):
                self.assertFalse(self.system.answer(f'72-month {product} APR?').confident)
                self.assertIn('12.49%', self.system.answer(f'60-month {product} APR?').text)

    def test_car_purchase_context_does_not_override_explicit_personal_loan(self):
        for purpose in ('to buy a 2021 car', 'for a used vehicle', 'to purchase a motorcycle',
                        'to add money to my savings'):
            answer = self.system.answer(f'60-month personal loan APR {purpose}?')
            self.assertIn('12.49%', answer.text)
            self.assertNotIn('5.64%', answer.text)
            self.assertEqual({s.url for s in answer.sources}, {PERSONAL_LOAN})

    def test_flex_and_fixed_use_separate_rows(self):
        md = '''# Certificate rates
| Term | Dividend Rate | APY | Minimum to Open |
| --- | --- | --- | --- |
| 6 Month Fixed | 3.30% | 3.40% | $1,000 |
| 6 Month Flex | 2.80% | 2.90% | $1,000 |
| 12 Month Fixed | 4.30% | 4.40% | $1,000 |
'''
        system = build(snapshot(page(PERSONAL, md)))
        for q in ('6-month flex certificate APY?', 'What are your flex certificate APYs?'):
            answer = system.answer(q)
            self.assertIn('2.90%', answer.text)
            self.assertNotIn('3.40%', answer.text)
            self.assertNotIn('4.40%', answer.text)
        answer = system.answer('6-month fixed certificate APY?')
        self.assertIn('3.40%', answer.text)
        self.assertNotIn('2.90%', answer.text)
        self.assertFalse(system.answer('12-month flex certificate APY?').confident)

    def test_missing_flex_schedule_cannot_fall_through(self):
        for url, text in [(PERSONAL, certs()),
                          ('https://example.test/rates/certificates', '6-month certificate APY: 4.25%')]:
            system = build(snapshot(page(url, text)))
            for q in ('6-month flex certificate APY?', 'Flex certificate rates?'):
                self.assertFalse(system.answer(q).confident)


class DateAndBranchIntentTests(unittest.TestCase):
    def setUp(self):
        self.system = build(snapshot(page(PERSONAL, certs()), date='2026-05-01'),
                            snapshot(page(PERSONAL, certs('4.50%')), date='2026-08-01', name='august'),
                            snapshot(page(PERSONAL, certs('5.00%')), date='2026-09-01', name='september'))

    def test_month_abbreviations_match_explicit_dates(self):
        for expression, expected, snap in [('Aug 2026', '4.50%', 'august'),
                                           ('Aug. 31, 2026', '4.50%', 'august'),
                                           ('August 2026', '4.50%', 'august'),
                                           ('Sept. 2026', '5.00%', 'september')]:
            with self.subTest(expression=expression):
                answer = self.system.answer(f'6-month certificate APY as of {expression}?')
                self.assertIn(expected, answer.text)
                self.assertEqual(answer.sources[0].snapshot_id, snap)

    def test_year_only_dates_do_not_default_to_present(self):
        for expression in ('in 2025', 'during 2025', 'as of 2025'):
            self.assertFalse(self.system.answer(f'6-month certificate APY {expression}?').confident)
        self.assertIn('5.00%', self.system.answer('6-month certificate APY in 2026?').text)

    def test_unrecognized_explicit_history_abstains(self):
        for expression in ('Smarch 2026', 'last spring', 'the old schedule'):
            self.assertFalse(self.system.answer(f'6-month certificate APY as of {expression}?').confident)

    def test_vehicle_year_remains_a_product_qualifier(self):
        auto = '''| Model Year | Term | APR |
| --- | --- | --- |
| 2024-27 Model Year | 60 Months | 5.39% APR |
'''
        system = build(snapshot(page(AUTO, auto), date='2026-05-01'))
        self.assertIn('5.39%', system.answer('60-month auto loan APR for a 2025 model vehicle?').text)

    def test_short_branch_names_cannot_inherit_generic_hours(self):
        system = build(snapshot(page('https://example.test/branches/harbor',
                                     '# Harbor Branch\n\n**Lobby**\n\nMonday-Friday: 9 a.m.-5 p.m.')))
        for name in ('Churchill', 'Atlantis', 'Rose Hill'):
            for prefix in (name, name + ' branch', name + "'s"):
                self.assertFalse(system.answer(f'{prefix} lobby hours?').confident)
        self.assertIn('9 a.m.-5 p.m.', system.answer('Harbor lobby hours?').text)
        self.assertTrue(system.answer('General lobby hours?').confident)
        self.assertTrue(system.answer('Do all Dupaco branches keep the same lobby hours?').confident)


def card_page(annual='0.00', cash='10.00', percent='3.00', intro='2.90', months=6):
    annual_text = 'There is no annual fee.' if annual == '0.00' else f'Annual fee: ${annual}.'
    return f'''# Cards
### Platinum Visa
Standard purchase APR: 12.50%–19.50% APR.
{annual_text}
Cash advance fee—${cash} or {percent}% of the amount of each cash advance, whichever is greater.
New cardmember offer: {intro}% intro APR on transferred balances for {months} months.
### Rewards Visa
Standard purchase APR: 15.50%–21.00% APR.
Annual fee: $19.00.
'''


class CardAttributeTests(unittest.TestCase):
    def test_fees_and_intro_are_read_from_the_requested_attribute(self):
        system = build(snapshot(page(PERSONAL_CARD, card_page())))
        questions = [('Does the Platinum Visa credit card charge an annual fee?', ('No annual fee',)),
                     ('Platinum Visa annual fees?', ('No annual fee',)),
                     ('Platinum Visa fee for cash advances?', ('$10.00', '3.00%', 'greater')),
                     ('Platinum Visa introductory balance transfer APR?', ('2.90%', '6 months'))]
        for q, expected in questions:
            with self.subTest(q=q):
                answer = system.answer(q)
                self.assertTrue(answer.confident)
                for value in expected:
                    self.assertIn(value.lower(), answer.text.lower())
                self.assertNotIn('12.50%', answer.text)
                self.assertEqual({s.url for s in answer.sources}, {PERSONAL_CARD})
                self.assertTrue(all(s.quote in card_page() for s in answer.sources))

    def test_updated_fees_and_duration_are_not_fixed_numbers(self):
        system = build(snapshot(page(PERSONAL_CARD, card_page(annual='39.00', cash='15.00', percent='4.00', intro='1.95', months=9))))
        self.assertIn('$39.00', system.answer('Platinum Visa annual fee?').text)
        cash = system.answer('Platinum Visa cash advance fee?')
        self.assertIn('$15.00', cash.text)
        self.assertIn('4.00%', cash.text)
        intro = system.answer('Platinum Visa intro APR?')
        self.assertIn('1.95%', intro.text)
        self.assertIn('9 months', intro.text)

    def test_card_details_do_not_leak_between_card_identities(self):
        system = build(snapshot(page(PERSONAL_CARD, card_page())))
        self.assertIn('$19.00', system.answer('Rewards Visa annual fee?').text)
        self.assertFalse(system.answer('Rewards Visa intro APR?').confident)
        self.assertFalse(system.answer('Business Platinum Visa annual fee?').confident)
        self.assertFalse(system.answer('Platinum Visa cash advance APR?').confident)

    def test_equal_authority_fee_disagreement_abstains(self):
        system = build(snapshot(page(PERSONAL_CARD, card_page()),
                                page(PERSONAL_CARD + '/', card_page(annual='39.00'))))
        self.assertFalse(system.answer('Platinum Visa annual fee?').confident)

    def test_both_families_and_single_family_are_distinct(self):
        business = '''| Card Type | APR |
| --- | --- |
| Business Platinum Visa | 16.00% |
| Business Rewards Visa | 22.00% |
'''
        system = build(snapshot(page(PERSONAL_CARD, card_page()), page(BUSINESS_CARD, business)))
        for scope, count in [('personal and business', 4), ('business and personal', 4),
                              ('personal', 2), ('business', 2), ('', 4)]:
            with self.subTest(scope=scope):
                answer = system.answer(f'What {scope} credit cards do you offer and what are their APRs?')
                self.assertTrue(answer.confident)
                self.assertEqual(answer.text.count('Visa:'), count)

    def test_standard_apr_is_separate_from_introductory_terms(self):
        system = build(snapshot(page(PERSONAL_CARD, card_page())))
        answer = system.answer('What is the standard Platinum Visa APR after the introductory offer?')
        self.assertIn('12.50%', answer.text)
        self.assertNotIn('2.90%', answer.text)


if __name__ == '__main__':
    unittest.main()
