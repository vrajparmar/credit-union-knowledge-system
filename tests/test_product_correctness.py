"""Product identity, date boundaries, and evidence-sensitive regression cases."""
import unittest

from test_regressions import AUTO, HOME, MORTGAGES, PERSONAL, build, certs, page, snapshot


CHECKING = 'https://example.test/personal/checking-accounts'
BUSINESS_CHECKING = 'https://example.test/business/checking-accounts'
PERSONAL_CARD = 'https://example.test/personal/credit-cards'
BUSINESS_CARD = 'https://example.test/business/credit-cards'
PERSONAL_LOAN = 'https://example.test/personal/loans/personal-loans'


def checking(rate='2.75%', balance_header='Balance Tier', business=False):
    prefix = 'Business ' if business else ''
    return f'''# Checking rates
| Account Type | {balance_header} | Dividend Rate | Annual Percentage Yield (APY)1 |
| --- | --- | --- | --- |
| {prefix}Free Checking | — | 0.00% | 0.00% |
| {prefix}1st Rate Checking | $0.01 – $4,999.99 | 0.00% | 0.00% |
| {prefix}1st Rate Checking | $5,000 – $24,999.99 | 2.72% | {rate} |
| {prefix}1st Rate Checking | $25,000 – $99,999.99 | 0.10% | 0.10% |
| {prefix}1st Rate Checking | $100,000+ | 0.20% | 0.20% |
'''


PROMO_CHECKING = '''# 1st Rate Checking
| Balance | Annual Percentage Yield (APY) |
| --- | --- |
| $5,000 – $24,999.99 | 3.00% |
'''


class CheckingEvidenceTests(unittest.TestCase):
    def test_headers_and_competing_promo_use_official_observation(self):
        for header in ('Balance', 'Balance Tier'):
            for rate in ('2.50%', '2.75%', '4.15%'):
                with self.subTest(header=header, rate=rate):
                    official = page(CHECKING, checking(rate, header))
                    promo = page('https://example.test/checking-offer-lp', PROMO_CHECKING)
                    system = build(snapshot(official, promo))
                    answer = system.answer('What is the APY on 1st Rate Checking for a $10,000 balance?')
                    self.assertTrue(answer.confident)
                    self.assertIn(rate, answer.text)
                    self.assertNotIn('3.00%', answer.text)
                    self.assertEqual({s.url for s in answer.sources}, {CHECKING})
                    self.assertTrue(answer.conflict_note)
                    conflicts = system.conflicts()
                    self.assertEqual(len(conflicts), 1)
                    self.assertEqual(conflicts[0].resolution, rate)
                    for value, source in zip(conflicts[0].values, conflicts[0].sources):
                        cited = official if source.url == CHECKING else promo
                        self.assertIn(value, source.quote)
                        self.assertIn(source.quote, cited.markdown)

    def test_balance_boundaries_and_currency_paraphrases(self):
        system = build(snapshot(page(CHECKING, checking())))
        for amount, expected in [('4,999.99', '0.00%'), ('5,000', '2.75%'),
                                 ('24,999.99', '2.75%'), ('25,000', '0.10%'),
                                 ('99,999.99', '0.10%'), ('100,000', '0.20%')]:
            with self.subTest(amount=amount):
                answer = system.answer(f'1st Rate Checking APY for a balance of {amount} dollars?')
                self.assertTrue(answer.confident)
                self.assertIn(expected, answer.text)
                self.assertEqual(answer.text.count(' APY '), 1)

    def test_personal_business_and_free_accounts_remain_separate(self):
        system = build(snapshot(page(CHECKING, checking()),
                                page(BUSINESS_CHECKING, checking('4.80%', business=True))))
        for qualifier, rate, url in [('personal', '2.75%', CHECKING),
                                     ('business', '4.80%', BUSINESS_CHECKING)]:
            answer = system.answer(f'{qualifier} 1st Rate Checking APY for $10k?')
            self.assertIn(rate, answer.text)
            self.assertEqual({s.url for s in answer.sources}, {url})
        self.assertEqual(system.conflicts(), [])
        answer = system.answer('Free Checking APY for $10k?')
        self.assertIn('0.00%', answer.text)
        self.assertNotIn('2.75%', answer.text)

    def test_equal_authority_disagreement_refuses(self):
        system = build(snapshot(page(CHECKING, checking()), page(CHECKING + '/', checking('2.90%'))))
        self.assertFalse(system.answer('1st Rate Checking APY for $10k?').confident)
        self.assertTrue(all(c.resolution is None for c in system.conflicts()))

    def test_missing_checking_data_does_not_generate_a_rate(self):
        system = build(snapshot(page(CHECKING, '# Checking\nContact us for account information.')))
        self.assertFalse(system.answer('Current checking interest rates?').confident)
        self.assertEqual(system.conflicts(), [])


class CardIdentityTests(unittest.TestCase):
    def setUp(self):
        personal = '''# Credit cards
### Platinum Visa
Standard purchase APR: 11.50%–18.50% APR.
Introductory transfer APR: 2.90% APR.
### Rewards Visa
Standard purchase APR: 14.20%–20.30% APR.
'''
        business = '''# Business cards
| Card Type | APR |
| --- | --- |
| Business Platinum Visa | 16.25% |
| Business Rewards Visa | 22.25% |
'''
        self.system = build(snapshot(page(PERSONAL_CARD, personal), page(BUSINESS_CARD, business)))

    def test_each_card_uses_its_own_observed_disclosure(self):
        for name, rates, url in [('Platinum Visa', ('11.50%', '18.50%'), PERSONAL_CARD),
                                 ('Rewards Visa', ('14.20%', '20.30%'), PERSONAL_CARD),
                                 ('Business Platinum Visa', ('16.25%',), BUSINESS_CARD),
                                 ('Business Rewards Visa', ('22.25%',), BUSINESS_CARD)]:
            with self.subTest(name=name):
                answer = self.system.answer(f'What is the standard purchase APR on the {name}?')
                self.assertTrue(answer.confident)
                self.assertIn(name, answer.text)
                for rate in rates:
                    self.assertIn(rate, answer.text)
                    self.assertIn(rate, answer.sources[0].quote)
                self.assertNotIn('2.90%', answer.text)
                self.assertEqual({s.url for s in answer.sources}, {url})
                self.assertEqual(answer.text.count('Visa:'), 1)

    def test_general_roster_and_business_scope(self):
        self.assertEqual(self.system.answer('Which credit cards and APRs do you offer?').text.count('Visa:'), 4)
        answer = self.system.answer('What are the business credit card APRs?')
        self.assertEqual(answer.text.count('Visa:'), 2)
        self.assertNotIn('11.50%', answer.text)

    def test_absent_card_does_not_borrow_personal_rate(self):
        system = build(snapshot(page(PERSONAL_CARD, '### Platinum Visa\nStandard purchase APR: 11.50%–18.50% APR.')))
        self.assertFalse(system.answer('Business Platinum Visa standard purchase APR?').confident)
        self.assertFalse(system.answer('Rewards Visa standard purchase APR?').confident)

    def test_card_apr_column_is_not_confused_with_cashback(self):
        table = '''| Card Type | Cashback | APR |
| --- | --- | --- |
| Business Rewards Visa | 2.00% | 22.25% |
'''
        system = build(snapshot(page(BUSINESS_CARD, table)))
        answer = system.answer('Business Rewards Visa standard purchase APR?')
        self.assertIn('22.25%', answer.text)
        self.assertNotIn('2.00%', answer.text)


class ExactProductTests(unittest.TestCase):
    def test_jumbo_negation_preserves_product(self):
        table = '''# Certificate rates
| Term | Dividend Rate | APY | Minimum to Open |
| --- | --- | --- | --- |
| 10 Month Fixed Special | 3.80% | 3.90% | $1,000 |
| 10 Month Fixed Jumbo Special | 3.90% | 4.00% | $100,000 |
'''
        system = build(snapshot(page(PERSONAL, table)))
        for qualifier in ('non-jumbo', 'non jumbo', 'not a jumbo', 'without jumbo'):
            with self.subTest(qualifier=qualifier):
                answer = system.answer(f'10-month {qualifier} certificate APY?')
                self.assertIn('3.90%', answer.text)
                self.assertNotIn('4.00%', answer.text)
        self.assertIn('4.00%', system.answer('10-month jumbo certificate APY?').text)

    def test_unlisted_personal_term_cannot_return_auto_rate(self):
        personal = '''| Term | APR |
| --- | --- |
| 36 Months | 10.49% APR |
| 60 Months | 12.49% APR |
'''
        auto = '''| Model Year | Term | APR |
| --- | --- | --- |
| 2024-27 Model Year | 72 Months | 5.49% APR |
'''
        system = build(snapshot(page(PERSONAL_LOAN, personal), page(AUTO, auto)))
        for term in ('72-month', 'seventy-two month', 'six-year'):
            self.assertFalse(system.answer(f'{term} personal loan APR?').confident)
        answer = system.answer('60-month personal loan APR?')
        self.assertIn('12.49%', answer.text)
        self.assertNotIn('5.49%', answer.text)
        self.assertEqual({s.url for s in answer.sources}, {PERSONAL_LOAN})

    def test_mortgage_program_and_rate_type_must_match(self):
        system = build(snapshot(page(HOME, MORTGAGES)))
        for product in ('FHA', 'VA', 'USDA', '5/1 ARM', '7/1 adjustable-rate', 'jumbo'):
            with self.subTest(product=product):
                self.assertFalse(system.answer(f'30-year {product} purchase mortgage rate?').confident)
        extra = '| Purchase: 30-Year Fixed FHA | 5.50% | 0 | 5.80% | $900 |\n'
        system = build(snapshot(page(HOME, MORTGAGES + extra)))
        answer = system.answer('30-year FHA purchase mortgage rate?')
        self.assertTrue(answer.confident)
        self.assertIn('5.50%', answer.text)
        self.assertNotIn('Conventional', answer.text)

    def test_mortgage_amount_wording_selects_same_tier(self):
        system = build(snapshot(page(HOME, MORTGAGES)))
        for amount in ('$100,000', '100,000 dollars', '100000 dollar loan', '100k',
                       'USD 100000', '100000 USD', '100,000 loan', 'loan amount of 100000'):
            with self.subTest(amount=amount):
                answer = system.answer(f'30-year conventional purchase mortgage rate for {amount}?')
                self.assertIn('6.80%', answer.text)
                self.assertNotIn('6.90%', answer.text)
                self.assertIn('6.95%', answer.text)

    def test_prose_certificate_term_is_exact(self):
        system = build(snapshot(page('https://example.test/rates/certificates',
                                     '6-month certificate APY: 4.25%\n12-month certificate APY: 4.50%')))
        for term in ('16-month', '36-month', 'thirty-six month'):
            self.assertFalse(system.answer(f'{term} certificate APY?').confident)
        self.assertIn('4.50%', system.answer('twelve-month certificate APY?').text)
        self.assertEqual(system.answer('six-month certificate APY?').text,
                         system.answer('6-month certificate APY?').text)

    def test_long_welcome_page_does_not_invent_conflicts(self):
        system = build(snapshot(page('https://www.dupaco.com/',
                                     '# Welcome\nWelcome to our credit union website. Contact us to learn more.')))
        self.assertEqual(system.conflicts(), [])

    def test_prose_rate_missing_from_current_snapshot_abstains(self):
        url = 'https://example.test/rates/certificates'
        system = build(snapshot(page(url, '6-month certificate APY: 4.25%')),
                       snapshot(page(url, 'Contact us for certificate information.'),
                                date='2026-03-01', name='later'))
        self.assertFalse(system.answer('6-month certificate APY?').confident)
        self.assertIn('4.25%', system.answer('6-month certificate APY?', '2026-02-01').text)


class CalendarAndAddressTests(unittest.TestCase):
    def setUp(self):
        self.system = build(snapshot(page(PERSONAL, certs()), date='2026-05-01'),
                            snapshot(page(PERSONAL, certs('5.00%')), date='2026-08-01', name='later'))

    def test_dates_outside_old_year_whitelist(self):
        self.assertFalse(self.system.answer('6-month certificate APY as of 2023-11-01?').confident)
        self.assertIn('5.00%', self.system.answer('6-month certificate APY as of 2027-11-01?').text)

    def test_date_removed_before_loan_type_matching(self):
        for text in ('7/1/2026', '7-1-2026', '2026-07-01', 'July 1, 2026', 'July 2026'):
            with self.subTest(text=text):
                answer = self.system.answer(f'6-month certificate APY as of {text}?')
                self.assertTrue(answer.confident)
                self.assertIn('4.10%', answer.text)
                self.assertEqual(answer.sources[0].snapshot_id, 'baseline')
        answer = self.system.answer('6-month certificate APY as of 7/1/2026?', '2026-08-01')
        self.assertIn('5.00%', answer.text)

    def test_invalid_dates_abstain(self):
        for date in ('2026-02-29', '2026-13-01', '2/30/2026', '2026-00-10'):
            with self.subTest(date=date):
                self.assertFalse(self.system.answer(f'6-month certificate APY as of {date}?').confident)
                self.assertFalse(self.system.answer('6-month certificate APY?', date).confident)

    def test_calendar_month_uses_leap_day(self):
        system = build(snapshot(page(PERSONAL, certs()), date='2024-02-28'),
                       snapshot(page(PERSONAL, certs('5.00%')), date='2024-02-29', name='leap'))
        self.assertIn('5.00%', system.answer('6-month certificate APY as of February 2024?').text)

    def test_similar_address_names_do_not_borrow_branch(self):
        contact = '''### Dupaco Credit Union Flint Hill Branch
2245 Flint Hill Dr., Dubuque, IA, 52003
### Dupaco Credit Union Operations Center
3999 Pennsylvania Ave., Dubuque, IA, 52002
'''
        system = build(snapshot(page('https://www.dupaco.com/contact', contact)))
        for name in ('Churchill', 'Rose Hill', 'Flint Ridge'):
            self.assertFalse(system.answer(f'Where is the {name} branch located?').confident)
        self.assertIn('2245 Flint Hill', system.answer('Where is the Flint Hill branch located?').text)
        self.assertIn('3999 Pennsylvania', system.answer('Where is the Operations Center located?').text)


if __name__ == '__main__':
    unittest.main()
