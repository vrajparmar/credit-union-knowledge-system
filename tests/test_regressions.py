"""Synthetic regression tests; no downloaded website corpus or API key needed."""
import dataclasses
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'hackathon-knowledge-kit-participant' / 'harness'))
from contract import Page, Snapshot
from run_eval import load_submission

PERSONAL = 'https://example.test/personal/savings-account'
BUSINESS = 'https://example.test/business/savings-accounts'
HOME = 'https://example.test/personal/loans/home-loans'
AUTO = 'https://example.test/personal/loans/auto-motorcycle-loans'


def page(url, markdown, title='Test schedule'):
    return Page(url=url, title=title, markdown=markdown, fetched_at='2026-01-01T00:00:00Z')


def snapshot(*pages, date='2026-01-01', name='baseline'):
    return Snapshot(snapshot_id=name, taken_on=date, pages=list(pages))


def build(*snapshots):
    system = load_submission(ROOT / 'submission')
    for snap in snapshots:
        system.ingest(snap)
    return system


def certs(six='4.10%'):
    return f'''# Certificate Rates
| Term | Dividend Rate | Annual Percentage Yield (APY) | Minimum to Open |
| --- | --- | --- | --- |
| 6 Month | 4.01% | {six} | $1,000 |
| 24 Month | 4.21% | 4.35% | $1,000 |
| 36 Month | 4.41% | 4.60% | $1,000 |
| 48 Month | 4.51% | 4.80% | $1,000 |
'''


MORTGAGES = '''# Home loan rates
| Program | Rate | Points | APR | Payment Example |
| --- | --- | --- | --- | --- |
| Purchase: 30-Year Fixed Conventional $300,000 or less | 6.90% | 0 | 7.02% | $1,000 |
| Purchase: 30-Year Fixed Conventional $100,000 or less | 6.80% | 0 | 6.95% | $600 |
| Purchase: 20-Year Fixed Conventional | 6.40% | 0 | 6.52% | $800 |
| Purchase: 15-Year Fixed Conventional | 6.10% | 0 | 6.22% | $900 |
| Refinance: 15-Year Fixed Conventional | 6.20% | 0 | 6.32% | $900 |
'''


class CertificateTests(unittest.TestCase):
    def setUp(self):
        self.system = build(snapshot(page(PERSONAL, certs())))

    def test_number_word_paraphrases(self):
        for word, term, rate in [('six', 6, '4.10%'), ('twenty-four', 24, '4.35%'),
                                 ('thirty-six', 36, '4.60%'), ('forty-eight', 48, '4.80%')]:
            for expression in (word, word.replace('-', ' ')):
                with self.subTest(expression=expression):
                    answer = self.system.answer(f'What is the APY on a {expression}-month certificate?')
                    control = self.system.answer(f'What is the APY on a {term}-month certificate?')
                    self.assertEqual(answer.text, control.text)
                    self.assertIn(rate, answer.text)

    def test_year_conversion(self):
        self.assertEqual(self.system.answer('APY on a two-year certificate?').text,
                         self.system.answer('APY on a 24-month certificate?').text)

    def test_unlisted_terms_and_jumbo_abstain(self):
        for term in ('7-month', 'four-month', '5-year jumbo', 'sixty-month jumbo'):
            with self.subTest(term=term):
                self.assertFalse(self.system.answer(f'What is the APY on a {term} certificate?').confident)

    def test_authority_beats_copies_and_business_is_separate(self):
        system = build(snapshot(page(PERSONAL, certs('5.00%')),
                                page('https://example.test/rates', certs('2.80%')),
                                page(BUSINESS, certs('6.00%'))))
        answer = system.answer('What is the personal 6-month certificate APY?')
        self.assertIn('5.00%', answer.text)
        self.assertNotIn('2.80%', answer.text)
        self.assertNotIn('6.00%', answer.text)
        self.assertEqual(answer.sources[0].url, PERSONAL)
        self.assertTrue(answer.conflict_note)
        self.assertIn('6.00%', system.answer('What is the business 6-month certificate APY?').text)

    def test_broad_list_resolves_authority(self):
        system = build(snapshot(page(PERSONAL, certs('5.00%')),
                                page('https://example.test/rates', certs('2.80%'))))
        answer = system.answer('List all certificate APYs.')
        self.assertIn('5.00%', answer.text)
        self.assertNotIn('2.80%', answer.text)

    def test_equal_authority_disagreement_abstains(self):
        system = build(snapshot(page(PERSONAL, certs('5.00%')),
                                page(PERSONAL + '/', certs('5.20%'))))
        self.assertFalse(system.answer('What is the personal 6-month certificate APY?').confident)
        self.assertTrue(any(c.resolution is None for c in system.conflicts()))

    def test_historical_snapshot_and_pre_crawl(self):
        self.system.ingest(snapshot(page(PERSONAL, certs('5.00%')), date='2026-03-01', name='update'))
        self.assertIn('4.10%', self.system.answer('6-month certificate APY?', '2026-02-01').text)
        self.assertIn('5.00%', self.system.answer('6-month certificate APY?').text)
        self.assertFalse(self.system.answer('6-month certificate APY?', '2025-01-01').confident)


class MortgageTests(unittest.TestCase):
    def setUp(self):
        self.system = build(snapshot(page(HOME, MORTGAGES)))

    def test_requested_term_and_purpose(self):
        for term, purpose, rate, apr in [(15, 'purchase', '6.10%', '6.22%'),
                                         (20, 'purchase', '6.40%', '6.52%'),
                                         (15, 'refinance', '6.20%', '6.32%')]:
            with self.subTest(term=term, purpose=purpose):
                answer = self.system.answer(f'What is the {term}-year conventional {purpose} mortgage rate?')
                self.assertIn(rate, answer.text)
                self.assertIn(apr, answer.text)
                self.assertNotIn('30-Year', answer.text)

    def test_amount_selects_smallest_applicable_tier(self):
        answer = self.system.answer('What is the 30-year purchase mortgage rate for $150,000?')
        self.assertIn('6.90%', answer.text)
        self.assertNotIn('6.80%', answer.text)

    def test_term_is_preserved_when_amount_supplied(self):
        answer = self.system.answer('What is the fifteen-year purchase mortgage rate for $100,000?')
        self.assertIn('6.10%', answer.text)
        self.assertNotIn('30-Year', answer.text)

    def test_unlisted_mortgage_term_abstains(self):
        self.assertFalse(self.system.answer('What is the 25-year mortgage rate?').confident)

    def test_historical_rate_changes(self):
        self.system.ingest(snapshot(page(HOME, MORTGAGES.replace('6.10%', '6.50%')),
                                    date='2026-03-01', name='update'))
        self.assertIn('6.10%', self.system.answer('15-year purchase mortgage rate?', '2026-02-01').text)
        self.assertIn('6.50%', self.system.answer('15-year purchase mortgage rate?').text)


class ConflictTests(unittest.TestCase):
    def test_only_observed_mortgage_values_and_provenance(self):
        official = page(HOME, MORTGAGES)
        guidance = page('https://example.test/homebuying-guidance', MORTGAGES.replace('6.90%', '6.00%'))
        baseline = snapshot(official, guidance)
        system = build(baseline)
        conflicts = system.conflicts()
        self.assertEqual(len(conflicts), 1)
        self.assertEqual(conflicts[0].resolution, '6.90%')
        self.assertNotIn('7.13%', conflicts[0].values)
        for conflict in conflicts:
            for value, source in zip(conflict.values, conflict.sources):
                self.assertEqual(source.snapshot_id, baseline.snapshot_id)
                cited = next(p for p in baseline.pages if p.url == source.url)
                self.assertIn(value, cited.markdown)
                self.assertTrue(source.quote)
                self.assertIn(source.quote, cited.markdown)

    def test_metrics_and_terms_do_not_create_false_conflicts(self):
        self.assertEqual(build(snapshot(page(HOME, MORTGAGES))).conflicts(), [])

    def test_changed_future_snapshot_updates_resolution(self):
        system = build(snapshot(page(HOME, MORTGAGES)))
        system.ingest(snapshot(page(HOME, MORTGAGES.replace('6.10%', '6.50%')),
                               name='later', date='2026-03-01'))
        conflicts = system.conflicts()
        self.assertEqual(len(conflicts), 1)
        self.assertEqual(conflicts[0].resolution, '6.50%')
        self.assertEqual({s.snapshot_id for s in conflicts[0].sources}, {'baseline', 'later'})

    def test_no_records_means_no_preset_conflicts(self):
        self.assertEqual(build(snapshot(page('https://www.dupaco.com/', '# Welcome'))).conflicts(), [])

    def test_fixture_host_and_numeric_format_do_not_determine_facts(self):
        official = page('https://renamed.test/rates/certificates', '6-month certificate APY: 4.25%')
        promo = page('https://renamed.test/promo', '6-month certificate APY: 3.00% (offer ended 2025-09-30)')
        system = build(snapshot(official, promo))
        self.assertEqual(system.conflicts()[0].resolution, '4.25%')
        same = dataclasses.replace(promo, markdown='6-month certificate APY: 4.250%')
        self.assertEqual(build(snapshot(official, same)).conflicts(), [])

    def test_auto_cohorts_are_compacted(self):
        table = '''| Model Year | Term | APR |
| --- | --- | --- |
| 2016 Model Year (and older) | 48 Months | 8.50% APR |
'''
        system = build(snapshot(page(AUTO, table), page('https://example.test/calculators/vehicle-affordability', table.replace('8.50%', '8.00%'))))
        self.assertEqual(len(system.conflicts()), 1)
        self.assertIn('2016 and older', system.conflicts()[0].topic)


class AutoAndCardTests(unittest.TestCase):
    def test_minimum_uses_schedule_and_keeps_conditions(self):
        table = '''| Model Year | Term | APR |
| --- | --- | --- |
| 2024-27 Model Year | 48 Months | 4.19% APR |
| 2024-27 Model Year | 60 Months | 4.39% APR |
| 2021-23 Model Year | 60 Months | 5.10% APR |
'''
        system = build(snapshot(page(AUTO, table)))
        answer = system.answer('What is the lowest auto loan APR?')
        self.assertIn('4.19%', answer.text)
        self.assertIn('48 Months', answer.text)
        self.assertNotIn('4.39%', answer.text)
        self.assertIn('5.10%', system.answer('60-month auto APR on a 2021 vehicle?').text)
        self.assertFalse(system.answer('36-month auto APR on a 2021 vehicle?').confident)

    def test_card_standard_apr_tracks_disclosure_without_wrong_intro(self):
        md = ('The 2.90% introductory annual percentage rate expires six months from the first transfer. '
              'Transfers must post during the first 90 days. The standard APR is a variable rate from '
              '11.50% APR to 18.50% APR based on creditworthiness.')
        system = build(snapshot(page('https://example.test/personal/credit-cards', md)))
        answer = system.answer('What is the standard purchase APR on the Platinum Visa?')
        self.assertIn('11.50%', answer.text)
        self.assertIn('18.50%', answer.text)
        self.assertNotIn('90 days', answer.text)


class BranchTests(unittest.TestCase):
    def setUp(self):
        self.system = build(snapshot(page('https://example.test/branches/harbor',
                                          '# Harbor Branch\n\n**Lobby**\n\nMonday-Friday: 9 a.m.-5 p.m.\n\n**Drive-up**\n\nMonday-Friday: 8 a.m.-6 p.m.')))

    def test_arbitrary_unknown_branches_abstain(self):
        for name in ('Atlantis', 'El Dorado', 'Fictional Heights'):
            for service in ('lobby', 'drive-up'):
                with self.subTest(name=name, service=service):
                    self.assertFalse(self.system.answer(f'What are the {service} hours for the {name} branch?').confident)

    def test_known_branch_uses_its_own_schedule(self):
        answer = self.system.answer('What are the lobby hours for the Harbor branch?')
        self.assertTrue(answer.confident)
        self.assertIn('9 a.m.-5 p.m.', answer.text)
        self.assertNotIn('8:30', answer.text)

    def test_general_hours_are_not_mistaken_for_a_branch_name(self):
        for question in ('What are the drive-up hours?', "What are Dupaco's general lobby hours?",
                         'Do all Dupaco branches keep the same lobby hours?'):
            with self.subTest(question=question):
                self.assertTrue(self.system.answer(question).confident)


class PackagingTests(unittest.TestCase):
    def test_compatibility_copy_matches_canonical_submission(self):
        for name in ('solution.py', 'NOTES.md', 'requirements.txt'):
            with self.subTest(name=name):
                self.assertEqual((ROOT / 'submission' / name).read_bytes(),
                                 (ROOT / 'hackathon-knowledge-kit-participant/submission' / name).read_bytes())


if __name__ == '__main__':
    unittest.main()
