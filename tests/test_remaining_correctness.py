"""Regression coverage for the eight additional submission-review findings."""
import itertools
import unittest

from test_regressions import AUTO, HOME, MORTGAGES, PERSONAL, build, page, snapshot
from test_product_correctness import CHECKING, PERSONAL_CARD, PERSONAL_LOAN, checking
from test_intent_and_evidence import card_page


AUTO_RATES = '''| Model Year | Term | APR |
| --- | --- | --- |
| 2024-27 Model Year | 60 Months | 5.39% APR |
'''
PERSONAL_RATES = '''| Term | APR |
| --- | --- |
| 60 Months | 12.49% APR |
'''
CERTIFICATES = '''# Certificate Rates
| Term | Dividend Rate | Annual Percentage Yield (APY) | Minimum to Open |
| --- | --- | --- | --- |
| 6 Month | 3.37% | 3.40% | $1,000 |
| 18 Month | 2.68% | 2.70% | $1,000 |
| 60 Month | 1.79% | 1.80% | $1,000 |
'''
CONTACT = 'https://www.dupaco.com/contact'
DIRECTORY = '''### Dupaco Credit Union
11375 Oldenburg Ln., Galena, IL, 61036
### Dupaco Credit Union
185 Peosta St., Peosta, IA, 52068
### Dupaco Flint Hill Branch
2245 Flint Hill Dr., Dubuque, IA, 52003
'''


class LoanConflictTests(unittest.TestCase):
    def test_apr_header_establishes_metric_without_repeated_cell_label(self):
        for url, md, rate, q in [
            (AUTO, AUTO_RATES, '5.39%', '60-month auto APR for a 2024 car?'),
            (PERSONAL_LOAN, PERSONAL_RATES, '12.49%', '60-month personal loan APR?'),
        ]:
            md = md.replace('| APR |', '| APR (As Low As) |').replace(rate + ' APR', rate + '1')
            system = build(snapshot(page(url, md)))
            answer = system.answer(q)
            self.assertTrue(answer.confident)
            self.assertIn(rate, answer.text)
            self.assertIn(answer.sources[0].quote, md)

    def test_mortgage_ties_abstain_in_both_source_orders(self):
        for metric, changed in [('rate', MORTGAGES.replace('6.80%', '7.80%')),
                                ('apr', MORTGAGES.replace('6.95%', '7.95%'))]:
            for pages in itertools.permutations([page(HOME, MORTGAGES), page(HOME + '/', changed)]):
                system = build(snapshot(*pages))
                for amount in ('', ' for $100,000'):
                    with self.subTest(metric=metric, order=pages[0].url, amount=amount):
                        answer = system.answer('30-year fixed conventional purchase mortgage rate' + amount + '?')
                        self.assertFalse(answer.confident)
                        self.assertIn('disagree', answer.text)
                        self.assertTrue(any(c.resolution is None for c in system.conflicts()))

    def test_same_value_formatting_is_not_a_loan_conflict(self):
        for url, md, original, formatted, q in [
            (HOME, MORTGAGES, '6.80%', '6.800%', '30-year mortgage rate for $100,000?'),
            (AUTO, AUTO_RATES, '5.39%', '5.390%', '60-month auto APR for a 2024 car?'),
            (PERSONAL_LOAN, PERSONAL_RATES, '12.49%', '12.490%', '60-month personal loan APR?'),
        ]:
            answers = []
            for pages in itertools.permutations([page(url, md), page(url + '/', md.replace(original, formatted))]):
                system = build(snapshot(*pages))
                answer = system.answer(q)
                self.assertTrue(answer.confident)
                self.assertIn(original, answer.text)
                self.assertEqual(system.conflicts(), [])
                answers.append(answer.text)
            self.assertEqual(*answers)

    def test_only_the_requested_mortgage_tier_needs_resolution(self):
        system = build(snapshot(page(HOME, MORTGAGES), page(HOME + '/', MORTGAGES.replace('6.90%', '7.90%'))))
        answer = system.answer('30-year purchase mortgage rate for $100,000?')
        self.assertTrue(answer.confident)
        self.assertIn('6.80%', answer.text)
        self.assertFalse(system.answer('30-year purchase mortgage rate for $150,000?').confident)

    def test_auto_and_personal_loan_ties_abstain(self):
        for url, md, old, new, q in [
            (AUTO, AUTO_RATES, '5.39%', '6.39%', '60-month auto APR for a 2024 car?'),
            (PERSONAL_LOAN, PERSONAL_RATES, '12.49%', '13.49%', '60-month personal loan APR?'),
        ]:
            for pages in itertools.permutations([page(url, md), page(url + '/', md.replace(old, new))]):
                system = build(snapshot(*pages))
                self.assertFalse(system.answer(q).confident)
                conflicts = system.conflicts()
                self.assertTrue(conflicts)
                self.assertTrue(all(c.resolution is None for c in conflicts))

    def test_overlapping_auto_cohorts_resolve_at_requested_year(self):
        extra = AUTO_RATES.replace('2024-27', '2026-29').replace('5.39%', '6.39%')
        system = build(snapshot(page(AUTO, AUTO_RATES), page(AUTO + '/', extra)))
        self.assertIn('5.39%', system.answer('60-month auto APR for a 2024 car?').text)
        self.assertFalse(system.answer('60-month auto APR for a 2026 car?').confident)
        self.assertFalse(system.answer('Lowest 60-month auto APR?').confident)

    def test_expired_copy_cannot_override_current_loan_schedule(self):
        for url, md, old, new, q in [
            (HOME, MORTGAGES, '6.80%', '7.80%', '30-year mortgage rate for $100,000?'),
            (AUTO, AUTO_RATES, '5.39%', '6.39%', '60-month auto APR for a 2024 car?'),
            (PERSONAL_LOAN, PERSONAL_RATES, '12.49%', '13.49%', '60-month personal loan APR?'),
        ]:
            expired = page(url + '/', md.replace(old, new) + '\nOffer ended 2025-01-01\n')
            for pages in itertools.permutations([page(url, md), expired]):
                system = build(snapshot(*pages))
                answer = system.answer(q)
                self.assertTrue(answer.confident)
                self.assertIn(old, answer.text)
                self.assertNotIn(new, answer.text)
                self.assertTrue(answer.conflict_note)
                self.assertEqual(system.conflicts()[0].resolution, old)

    def test_new_snapshot_resolves_earlier_personal_loan_disagreement(self):
        system = build(snapshot(page(PERSONAL_LOAN, PERSONAL_RATES),
                                page(PERSONAL_LOAN + '/', PERSONAL_RATES.replace('12.49%', '13.49%'))),
                       snapshot(page(PERSONAL_LOAN, PERSONAL_RATES.replace('12.49%', '11.49%')),
                                name='later', date='2026-08-01'))
        self.assertFalse(system.answer('60-month personal loan APR?', '2026-06-01').confident)
        answer = system.answer('60-month personal loan APR?')
        self.assertTrue(answer.confident)
        self.assertIn('11.49%', answer.text)
        self.assertEqual(system.conflicts()[0].resolution, '11.49%')


class NumericConstraintTests(unittest.TestCase):
    def test_decimal_years_are_equivalent_to_whole_months(self):
        system = build(snapshot(page(PERSONAL, CERTIFICATES)))
        for term, months in [('1.5-year', '18-month'), ('1.50 years', '18 months'),
                              ('0.5-year', '6-month'), ('.5 years', '6 months')]:
            self.assertEqual(system.answer(f'{term} certificate APY?').text,
                             system.answer(f'{months} certificate APY?').text)

    def test_invalid_or_partial_terms_do_not_become_broad_requests(self):
        system = build(snapshot(page(PERSONAL, CERTIFICATES)))
        for term in ('1.1-year', '1.2.5-year', '0-month', '-1.5-year', '6.5 months', '3/2-year'):
            with self.subTest(term=term):
                self.assertFalse(system.answer(f'{term} certificate APY?').confident)

    def test_negative_balance_signs_are_preserved(self):
        system = build(snapshot(page(CHECKING, checking())))
        for amount in ('-$10,000', '$-10,000', '−$10,000', '-10000 dollars', '-10k', 'USD -10000', '-10000 USD'):
            for product in ('1st Rate Checking', 'Free Checking'):
                with self.subTest(amount=amount, product=product):
                    self.assertFalse(system.answer(f'{product} APY for a {amount} balance?').confident)
        self.assertIn('2.75%', system.answer('1st Rate Checking APY for a +$10,000 balance?').text)

    def test_negative_or_zero_mortgage_amounts_abstain(self):
        system = build(snapshot(page(HOME, MORTGAGES)))
        for amount in ('-$100,000', '$-100,000', '$0'):
            self.assertFalse(system.answer(f'30-year mortgage rate for {amount}?').confident)

    def test_unpublished_model_years_are_not_wildcards(self):
        system = build(snapshot(page(AUTO, AUTO_RATES)))
        for year in (2030, 2035, 2100, 1899):
            for phrase in (f'for a {year} car', f'for model year {year}', f'for vehicle {year}'):
                with self.subTest(phrase=phrase):
                    self.assertFalse(system.answer(f'60-month auto loan APR {phrase}?').confident)

    def test_published_future_cohorts_and_amounts_are_handled(self):
        system = build(snapshot(page(AUTO, AUTO_RATES.replace('2024-27', '2030-32'))))
        self.assertIn('5.39%', system.answer('60-month auto APR for a 2031 car?').text)
        system = build(snapshot(page(AUTO, AUTO_RATES)))
        self.assertIn('5.39%', system.answer('60-month auto APR for a $2030 loan?').text)


class ProductConstraintTests(unittest.TestCase):
    def test_unknown_card_name_or_network_does_not_borrow_a_rate(self):
        system = build(snapshot(page(PERSONAL_CARD, card_page())))
        for product in ('Gold Visa', 'Platinum Mastercard', 'Gold Platinum Visa',
                        'Premier credit card', 'credit card named Gold', 'Gold Visa credit card'):
            with self.subTest(product=product):
                self.assertFalse(system.answer(f'What is the APR on the {product}?').confident)
        self.assertIn('12.50%', system.answer('Platinum Visa credit card APR?').text)

    def test_mortgage_product_and_payment_structure_are_required(self):
        system = build(snapshot(page(HOME, MORTGAGES)))
        for qualifier in ('commercial', 'business', 'interest-only', 'interest only', 'balloon', 'reverse'):
            with self.subTest(qualifier=qualifier):
                self.assertFalse(system.answer(f'30-year {qualifier} mortgage rate for $100,000?').confident)
        self.assertIn('6.80%', system.answer('30-year fixed conventional mortgage rate for $100,000?').text)

    def test_published_interest_only_program_can_answer(self):
        md = MORTGAGES + '| Purchase: 30-Year Interest-Only Conventional | 5.10% | 0 | 5.25% | $600 |\n'
        system = build(snapshot(page(HOME, md)))
        answer = system.answer('30-year interest-only conventional purchase mortgage APR?')
        self.assertTrue(answer.confident)
        self.assertIn('5.25%', answer.text)
        self.assertNotIn('6.80%', answer.text)

    def test_unknown_branch_name_cannot_be_replaced_by_city(self):
        system = build(snapshot(page(CONTACT, DIRECTORY)))
        for name in ('Churchill', 'Atlantis', 'Rose Hill'):
            for phrase in (f'the {name} branch in Galena', f'the branch named {name} in Galena',
                           f'the {name} branch in Peosta'):
                self.assertFalse(system.answer(f'Where is {phrase}?').confident)
        self.assertFalse(system.answer('Where is the Flint Hill branch in Galena?').confident)

    def test_supported_branch_identity_and_city_both_match(self):
        system = build(snapshot(page(CONTACT, DIRECTORY)))
        for q, address in [('Where is the Galena branch?', '11375 Oldenburg'),
                           ('What is the address of the Peosta branch?', '185 Peosta'),
                           ('Where is the Flint Hill branch in Dubuque?', '2245 Flint Hill'),
                           ('Where is the Key West branch?', '2245 Flint Hill')]:
            self.assertIn(address, system.answer(q).text)

    def test_new_published_branch_and_updated_address_are_used(self):
        md = DIRECTORY.replace('11375 Oldenburg Ln.', '999 River Rd.') + '\n### Dupaco Churchill Branch\n101 Oak St., Galena, IL, 61036\n'
        system = build(snapshot(page(CONTACT, md)))
        answer = system.answer('Where is the Churchill branch in Galena?')
        self.assertTrue(answer.confident)
        self.assertIn('101 Oak', answer.text)
        self.assertNotIn('11375', system.answer('Where is the Galena branch?').text)


class MultiAttributeCardTests(unittest.TestCase):
    def test_normal_question_words_are_not_card_identity_constraints(self):
        system = build(snapshot(page(PERSONAL_CARD, card_page())))
        for q in ('Does the Platinum Visa have an annual fee?',
                  'Does my Platinum Visa credit card have an annual fee?',
                  'What annual fee does the Platinum Visa have?'):
            self.assertIn('No annual fee', system.answer(q).text)

    def test_requested_card_attributes_are_all_answered_in_any_order(self):
        system = build(snapshot(page(PERSONAL_CARD, card_page())))
        for attributes in itertools.permutations(['annual fee', 'standard purchase APR', 'cash advance fee']):
            answer = system.answer('What are the ' + ' and '.join(attributes) + ' on the Platinum Visa credit card?')
            self.assertTrue(answer.confident)
            for value in ('No annual fee', '12.50%', '19.50%', '$10.00', '3.00%'):
                self.assertIn(value, answer.text)
            self.assertTrue(all(source.quote in card_page() for source in answer.sources))

    def test_default_purchase_apr_and_intro_apr_remain_separate(self):
        system = build(snapshot(page(PERSONAL_CARD, card_page())))
        for q in ('Platinum Visa annual fee and APR?', 'Platinum Visa APR and cash advance fee?'):
            self.assertIn('12.50%', system.answer(q).text)
        answer = system.answer('Platinum Visa standard APR and introductory APR?')
        self.assertIn('12.50%', answer.text)
        self.assertIn('2.90%', answer.text)
        self.assertIn('6 months', answer.text)

    def test_missing_or_conflicting_requested_detail_cannot_be_silent(self):
        system = build(snapshot(page(PERSONAL_CARD, card_page())))
        for q in ('Rewards Visa annual fee and cash advance fee?',
                  'Platinum Visa annual fee and late fee?',
                  'Platinum Visa annual fee and cash advance APR?'):
            self.assertFalse(system.answer(q).confident)
        system = build(snapshot(page(PERSONAL_CARD, card_page()),
                                page(PERSONAL_CARD + '/', card_page(cash='15.00'))))
        self.assertFalse(system.answer('Platinum Visa annual fee and cash advance fee?').confident)

    def test_multiple_attributes_follow_changed_and_historical_evidence(self):
        later = card_page(annual='39.00', cash='15.00', percent='4.00').replace('12.50%', '11.50%')
        system = build(snapshot(page(PERSONAL_CARD, card_page())),
                       snapshot(page(PERSONAL_CARD, later), name='later', date='2026-08-01'))
        q = 'Platinum Visa annual fee and APR and cash advance fee?'
        answer = system.answer(q)
        for value in ('$39.00', '11.50%', '$15.00', '4.00%'):
            self.assertIn(value, answer.text)
        self.assertTrue(all(s.quote in later and s.snapshot_id == 'later' for s in answer.sources))
        self.assertIn('No annual fee', system.answer(q, '2026-06-01').text)


if __name__ == '__main__':
    unittest.main()
