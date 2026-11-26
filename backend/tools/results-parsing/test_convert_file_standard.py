import csv
import json
import os
import tempfile
import unittest

import convert_file_standard as convert

SCORE_HEADER = ['Event Name', 'Discipline', 'Age Category', 'Session Start Date', 'Round', 'Part', 'Apparatus',
                'Rank', 'Bib', 'Total']
SUMMARY_HEADER = ['Event Name', 'Discipline', 'Age Category', 'Event Start Date', 'Round', 'Part', 'Rank',
                  'NOC Code', 'Total', 'Scores Round']


class ConvertTest(unittest.TestCase):

    def setUp(self):
        self.dir = tempfile.mkdtemp()

    def write_csv(self, name, header, rows):
        with open(os.path.join(self.dir, name), 'w', newline='', encoding='utf-8') as f:
            w = csv.writer(f, lineterminator='\n')
            w.writerow(header)
            w.writerows(rows)

    def read_csv(self, name):
        with open(os.path.join(self.dir, name), newline='', encoding='utf-8') as f:
            return list(csv.reader(f))

    def write_manifest(self, prefix, scores, summaries, judges=()):
        manifest = {'event': {'title': 'Test', 'disciplines': 'MAG', 'ageCategory': 'SR'},
                    'participants': [], 'judges': list(judges), 'scores': scores, 'summaries': summaries}
        with open(os.path.join(self.dir, f'{prefix}-IMPORT.json'), 'w') as f:
            json.dump(manifest, f)

    def read_manifest(self, prefix):
        with open(os.path.join(self.dir, f'{prefix}-IMPORT.json')) as f:
            return json.load(f)

    def snapshot(self):
        files = {}
        for name in sorted(os.listdir(self.dir)):
            with open(os.path.join(self.dir, name), encoding='utf-8') as f:
                files[name] = f.read()
        return files

    def test_qualification_meet(self):
        self.write_csv('P-SCORES-QUAL-FX.csv', SCORE_HEADER, [['T', 'MAG', 'SR', '2026-10-18', 'QUAL', '', 'FX',
                                                             '1', '7', '14.000']])
        self.write_csv('P-SCORES-TEAM-FX.csv', SCORE_HEADER, [['T', 'MAG', 'SR', '2026-10-20', 'TEAM', '', 'FX',
                                                             '', '7', '14.100']])
        self.write_csv('P-SUMMARY-FINAL-TEAM.csv', SUMMARY_HEADER, [['T', 'MAG', 'SR', '2026-10-17', 'TEAM', '',
                                                                   '1', 'JPN', '250.000', '']])
        self.write_csv('P-SUMMARY-FINAL-AA.csv', SUMMARY_HEADER, [['T', 'MAG', 'SR', '2026-10-17', 'AA', '',
                                                                 '', 'JPN', '80.000', 'QUAL']])
        self.write_csv('P-JUDGES.csv', ['Round', 'Apparatus', 'Function'], [['EVENT', 'FX', 'D1']])
        self.write_manifest('P', ['P-SCORES-QUAL-FX.csv', 'P-SCORES-TEAM-FX.csv'],
                            ['P-SUMMARY-FINAL-AA.csv', 'P-SUMMARY-FINAL-TEAM.csv'], ['P-JUDGES.csv'])

        convert.main([self.dir])

        manifest = self.read_manifest('P')
        self.assertEqual(['P-SCORES-C1-FX.csv', 'P-SCORES-C4-FX.csv'], manifest['scores'])
        self.assertEqual(['P-RANKING-FINAL-AA.csv', 'P-RANKING-FINAL-TEAM.csv'], manifest['rankings'])
        self.assertNotIn('summaries', manifest)
        self.assertFalse(os.path.exists(os.path.join(self.dir, 'P-SCORES-QUAL-FX.csv')))
        self.assertEqual(['Event Name', 'Discipline', 'Age Category', 'Competition Start Date', 'Competition',
                          'Part', 'Apparatus', 'Rank', 'Bib', 'Total'], self.read_csv('P-SCORES-C1-FX.csv')[0])
        self.assertEqual('C1', self.read_csv('P-SCORES-C1-FX.csv')[1][4])
        team = self.read_csv('P-RANKING-FINAL-TEAM.csv')
        self.assertEqual(['Event Name', 'Discipline', 'Age Category', 'Event Start Date', 'Competition', 'Part',
                          'Purpose', 'Rank', 'Rank Status', 'NOC Code', 'Total'], team[0])
        self.assertEqual(['T', 'MAG', 'SR', '2026-10-17', 'C4', '', 'FINAL', '1', '', 'JPN', '250.000'], team[1])
        # The Scores Round names the competition ranked
        self.assertEqual('C1', self.read_csv('P-RANKING-FINAL-AA.csv')[1][4])
        self.assertEqual([['Competition', 'Apparatus', 'Function'], ['C3', 'FX', 'D1']],
                         self.read_csv('P-JUDGES.csv'))

    def test_single_competition_meet_is_c1(self):
        self.write_csv('P-SCORES-AA-FX.csv', SCORE_HEADER, [['T', 'MAG', 'SR', '2026-08-06', 'AA', '1', 'FX',
                                                           '1', '7', '14.000']])
        self.write_csv('P-SUMMARY-FINAL-AA.csv', SUMMARY_HEADER, [
            ['T', 'MAG', 'SR', '2026-08-06', 'AA', '1', '', 'USA', '80.000', ''],
            ['T', 'MAG', 'SR', '2026-08-06', 'AA', '', '1', 'USA', '160.000', '']])
        self.write_csv('P-SUMMARY-FINAL-TEAM.csv', SUMMARY_HEADER, [['T', 'MAG', 'SR', '2026-08-06', 'TEAM', '',
                                                                   '1', 'AUS', '250.000', 'AA']])
        self.write_manifest('P', ['P-SCORES-AA-FX.csv'], ['P-SUMMARY-FINAL-AA.csv', 'P-SUMMARY-FINAL-TEAM.csv'])

        convert.main([self.dir])

        self.assertEqual(['P-SCORES-C1-FX.csv'], self.read_manifest('P')['scores'])
        aa = self.read_csv('P-RANKING-FINAL-AA.csv')
        self.assertEqual(['C1', '1', 'INFORMATIONAL'], aa[1][4:7])
        self.assertEqual(['C1', '', 'FINAL'], aa[2][4:7])
        self.assertEqual('C1', self.read_csv('P-RANKING-FINAL-TEAM.csv')[1][4])

    def test_formats_come_from_the_event_file(self):
        self.write_csv('P-SCORES-QUAL-FX.csv', SCORE_HEADER, [['T', 'MAG', 'SR', '2026-10-18', 'QUAL', '', 'FX',
                                                             '1', '7', '14.000']])
        self.write_csv('X-EVENT.csv', ['Prefix', 'Title', 'Team Format', 'AA Format', 'Apparatus Format'],
                       [['P', 'Test', 'NONE', 'NONE', 'FINAL']])
        self.write_manifest('P', ['P-SCORES-QUAL-FX.csv'], [])

        convert.main([self.dir])

        event = self.read_manifest('P')['event']
        self.assertEqual(('NONE', 'NONE', 'FINAL'), (event['teamFormat'], event['aaFormat'],
                                                     event['apparatusFormat']))

    def test_running_again_changes_nothing(self):
        self.write_csv('P-SCORES-QUAL-FX.csv', SCORE_HEADER, [['T', 'MAG', 'SR', '2026-10-18', 'QUAL', '', 'FX',
                                                             '1', '7', '14.000']])
        self.write_csv('P-SUMMARY-QUAL-AA.csv', SUMMARY_HEADER, [['T', 'MAG', 'SR', '2026-10-17', 'QUAL', '', '1',
                                                                'JPN', '80.000', '']])
        self.write_manifest('P', ['P-SCORES-QUAL-FX.csv'], ['P-SUMMARY-QUAL-AA.csv'])

        convert.main([self.dir])
        once = self.snapshot()
        convert.main([self.dir])

        self.assertEqual(once, self.snapshot())
        self.assertEqual('QUALIFYING', self.read_csv('P-RANKING-QUAL-AA.csv')[1][6])

    def test_unknown_round_fails(self):
        self.write_csv('P-SCORES-QUAL-FX.csv', SCORE_HEADER, [['T', 'MAG', 'SR', '2026-10-18', 'SEMI', '', 'FX',
                                                             '1', '7', '14.000']])
        self.write_manifest('P', ['P-SCORES-QUAL-FX.csv'], [])

        with self.assertRaises(SystemExit):
            convert.main([self.dir])


if __name__ == '__main__':
    unittest.main()
