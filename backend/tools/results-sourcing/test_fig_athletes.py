"""Tests for fig_athletes.py. Run from the repo root:

    python3 -I -m unittest discover -s backend/tools/results-sourcing
"""
import datetime, io, json, os, sys, tempfile, unittest
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import fig_athletes as fa

def record(license='70193', surname='GHADIMI', given='Mehrdad', country='QAT', birth='2003-06-16',
           discipline='MAG', gymnast='111770'):
    return {'idgymnastlicense': license, 'gymnastid': gymnast, 'discipline': discipline,
            'validto': '2028-06-08', 'licensestatus': '2026-06-08', 'preferredlastname': surname,
            'preferredfirstname': given, 'birth': birth, 'gender': 'male', 'country': country}

def fig_row(**values):
    rows = []
    fa.merge(rows, [record(**values)], '2026-11-01')
    return rows[0]

def entry(surname='GHADIMI', given='Mehrdad', noc='QAT', license='70193', dob='', year='2003',
          discipline='MAG'):
    return {'Discipline': discipline, 'NOC Code': noc, 'Bib Number': '101', 'FIG License': license,
            'Surname': surname, 'Given Name': given, 'Birth Year': year, 'Birth Date': dob}

class FigSiteTest(unittest.TestCase):
    def test_parse_records(self):
        self.assertEqual(fa.parse_records(json.dumps([record()]).encode())[0]['idgymnastlicense'], '70193')

    def test_parse_records_fails_clearly_when_the_endpoint_changes(self):
        for body in (b'<html>error</html>', b'{"data": []}', json.dumps([{'id': 1}]).encode()):
            with self.assertRaises(SystemExit) as e:
                fa.parse_records(body)
            self.assertIn('may have changed', str(e.exception))

class MergeTest(unittest.TestCase):
    def test_new_license_is_added_with_its_seen_dates(self):
        rows = []
        added, changed = fa.merge(rows, [record()], '2026-11-27')
        self.assertEqual(len(added), 1)
        self.assertEqual(rows[0]['Surname'], 'GHADIMI')
        self.assertEqual(rows[0]['Birth Date'], '2003-06-16')
        self.assertEqual((rows[0]['First Seen'], rows[0]['Last Seen']), ('2026-11-27', '2026-11-27'))

    def test_listed_again_updates_last_seen_and_reports_changes(self):
        rows = [fig_row()]
        added, changed = fa.merge(rows, [record(birth='2003-06-17')], '2026-11-27')
        self.assertEqual(added, [])
        self.assertEqual(len(changed), 1)
        self.assertEqual(rows[0]['Birth Date'], '2003-06-17')
        self.assertEqual((rows[0]['First Seen'], rows[0]['Last Seen']), ('2026-11-01', '2026-11-27'))

    def test_renewal_alone_is_not_a_change(self):
        renewed = {**record(), 'licensestatus': '2028-06-08', 'validto': '2030-06-08'}
        rows = [fig_row()]
        self.assertEqual(fa.merge(rows, [renewed], '2026-11-27'), ([], []))
        self.assertEqual(rows[0]['Valid To'], '2030-06-08')

    def test_sync_keeps_licenses_no_longer_listed(self):
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, 'FIG-LICENSES.csv')
            fa.write_fig_licenses([fig_row(), fig_row(license='1', surname='ABAD', given='Nestor')], path)
            with mock.patch.object(fa, 'search_licenses', return_value=[record()]), \
                    mock.patch('sys.stdout', io.StringIO()) as out:
                rows = fa.sync(['MAG'], path=path)
            self.assertIn('1 no longer listed', out.getvalue())
            self.assertEqual(sorted(r['FIG License'] for r in rows), ['1', '70193'])
            kept = next(r for r in fa.read_rows(path) if r['FIG License'] == '1')
            self.assertEqual(kept['Last Seen'], '2026-11-01')

    def test_sync_within_max_age_downloads_nothing(self):
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, 'FIG-LICENSES.csv')
            row = fig_row()
            row['Last Seen'] = datetime.date.today().isoformat()
            fa.write_fig_licenses([row], path)
            with mock.patch.object(fa, 'search_licenses') as search, mock.patch('sys.stdout', io.StringIO()):
                fa.sync(['MAG'], max_age=30, path=path)
            search.assert_not_called()

class NamesTest(unittest.TestCase):
    def test_name_key(self):
        self.assertEqual(fa.name_key('  ECHEVERRÍA-López '), 'echeverria lopez')
        self.assertEqual(fa.name_key('BRONSHTEIN`'), 'bronshtein')

    def test_same_name(self):
        self.assertTrue(fa.same_name('AJALLA', 'Isabella Ayelen', 'AJALLA', 'Isabella'))
        self.assertTrue(fa.same_name('AL SHAMI', 'Lamar', 'ALSHAMI', 'Lamar'))
        self.assertTrue(fa.same_name('AL-HARITH', 'Rakan', 'RAKAN', 'Al-Harith'))
        self.assertFalse(fa.same_name('ANDRADE', 'Bernardo', 'MIRANDA', 'Bernardo'))

    def test_same_country(self):
        self.assertTrue(fa.same_country('QAT', 'QAT'))
        self.assertTrue(fa.same_country('SCO', 'GBR'))
        self.assertTrue(fa.same_country('AIN', 'BLR'))
        self.assertFalse(fa.same_country('QAT', 'BRN'))

class CompareTest(unittest.TestCase):
    def reference(self, fig=None, hand=None):
        return fa.Reference(fig if fig is not None else [fig_row()], hand or [])

    def test_agreeing_entry_has_no_differences(self):
        self.assertEqual(fa.compare(entry(dob='2003-06-16'), self.reference()), [])

    def test_unknown_license(self):
        self.assertEqual(fa.compare(entry(license='99'), self.reference()),
                         ['FIG lists no license 99 (lapsed, or misprinted)'])

    def test_birth_date_and_year_differences(self):
        self.assertEqual(fa.compare(entry(dob='2003-06-15'), self.reference()),
                         ['FIG has born 2003-06-16, not 2003-06-15'])
        self.assertEqual(fa.compare(entry(year='2004'), self.reference()),
                         ['FIG has born 2003-06-16, not in 2004'])

    def test_name_country_and_discipline_differences(self):
        issues = fa.compare(entry(surname='GHADIRI', noc='BRN', discipline='WAG'), self.reference())
        self.assertEqual(issues, ['FIG license 70193 is MAG', 'FIG names license 70193 GHADIMI Mehrdad',
                                  'FIG lists license 70193 under QAT'])

    def test_unlicensed_entry_gets_a_suggestion_only_from_one_match(self):
        self.assertEqual(fa.compare(entry(license=''), self.reference()),
                         ['no license printed; FIG lists 70193 for this name and country, born 2003-06-16'])
        twins = [fig_row(), fig_row(license='2', gymnast='2')]
        self.assertEqual(fa.compare(entry(license=''), self.reference(twins)),
                         ['no license printed; FIG lists 70193, 2 for this name and country'])
        self.assertEqual(fa.compare(entry(license='', noc='BRN'), self.reference()), [])

    def test_hand_curated_birth_date_is_compared(self):
        hand = [{'Discipline': 'MAG', 'NOC Code': 'QAT', 'FIG License': '', 'Surname': 'Ghadimi',
                 'Given Name': 'Mehrdad', 'Birth Date': '2003-06-15', 'Source': 'QGF', 'Note': ''}]
        self.assertEqual(fa.compare(entry(license='', dob='2003-06-15'), self.reference(fig=[], hand=hand)), [])
        self.assertEqual(fa.compare(entry(license='', dob='2003-06-14'), self.reference(fig=[], hand=hand)),
                         ['ATHLETES.csv has born 2003-06-15, not 2003-06-14'])

class FilesTest(unittest.TestCase):
    def write(self, d, name, text):
        path = os.path.join(d, name)
        with open(path, 'w', encoding='utf-8') as f:
            f.write(text)
        return path

    def test_check_reads_folders_and_carries_the_noc_down(self):
        with tempfile.TemporaryDirectory() as d:
            self.write(d, 'X-MAG-SR-PARTICIPANTS.csv',
                       'Discipline,NOC Code,Bib Number,FIG License,Surname,Given Name,Birth Year,Birth Date\n'
                       'MAG,QAT,1,70193,GHADIMI,Mehrdad,2003,\n'
                       'MAG,,2,70193,GHADIMI,Mehrdad,2004,\n')
            out = io.StringIO()
            self.assertEqual(fa.check([d], fa.Reference([fig_row()], []), out), 1)
            self.assertIn('line 3 bib 2 GHADIMI Mehrdad (QAT): FIG has born 2003-06-16, not in 2004', out.getvalue())

    def test_missing_lists_athletes_no_source_dates(self):
        with tempfile.TemporaryDirectory() as d:
            self.write(d, 'X-MAG-SR-PARTICIPANTS.csv',
                       'Discipline,NOC Code,Bib Number,FIG License,Surname,Given Name,Birth Year,Birth Date\n'
                       'MAG,QAT,1,70193,GHADIMI,Mehrdad,2003,\n'
                       'MAG,QAT,2,,AHMED,Ali,2001,\n'
                       'MAG,QAT,3,,SALEH,Omar,1999,1999-01-02\n')
            self.write(d, 'Y-MAG-SR-PARTICIPANTS.csv',
                       'Discipline,NOC Code,Bib Number,FIG License,Surname,Given Name,Birth Year,Birth Date\n'
                       'MAG,QAT,1,,AHMED,Ali,2001,\n')
            rows = fa.missing([d], fa.Reference([fig_row()], []))
            self.assertEqual([(r['Surname'], r['Note']) for r in rows], [('AHMED', 'born 2001')])

if __name__ == '__main__':
    unittest.main()
