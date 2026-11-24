"""Tests for fig_events.py. Run from the repo root:

    python3 -I -m unittest discover -s backend/tools/results-sourcing
"""
import csv, os, sys, tempfile, unittest
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import fig_events as fe

def detail(fig_id=18608, level='Continental Games', disciplines=None, files=None, **extra):
    return {
        'id': fig_id, 'title': ' 20th Asian Games Aichi-Nagoya 2026 ', 'status': 'approved',
        'startEvent': '2026-09-21', 'endEvent': '2026-10-04',
        'city': {'name': 'NAGOYA', 'country': {'name': 'Japan', 'code': 'JPN'}},
        'venue': 'Nagoya City Rainbow Hall', 'level': {'name': level},
        'apparatusSuppliers': [{'name': 'Taishan Sports Equipment'}],
        'disciplines': disciplines if disciplines is not None else [
            {'code': 'MAG', 'agecategories': [{'name': 'Senior'}]},
            {'code': 'WAG', 'agecategories': [{'name': 'Junior'}, {'name': 'Senior'}]},
            {'code': 'RGI', 'agecategories': [{'name': 'Senior'}]}],
        'files': files or [], **extra}

class ValuesTest(unittest.TestCase):
    def test_city_name(self):
        self.assertEqual(fe.city_name('BRISBANE, QLD'), 'Brisbane')
        self.assertEqual(fe.city_name('JESOLO (VE)'), 'Jesolo')
        self.assertEqual(fe.city_name('RIO DE JANEIRO'), 'Rio de Janeiro')
        self.assertEqual(fe.city_name('STOKE-ON-TRENT'), 'Stoke-on-Trent')

    def test_media_book_preferred_over_delegation_and_api(self):
        files = [{'title': 'Results book (Delegation)', 'url': '../../asset.php?id=fidb_24368'},
                 {'title': 'Results book (Media)', 'url': '../../asset.php?id=fidb_24389'},
                 {'title': '7_Drawing of Lots - Results', 'url': '../../asset.php?id=fidb_24252'}]
        self.assertEqual(fe.media_book(detail(files=files), {'resultbook': 24368}), 24389)

    def test_media_book_falls_back_to_results_api(self):
        self.assertEqual(fe.media_book(detail(), {'resultbook': 21495}), 21495)
        self.assertIsNone(fe.media_book(detail(), None))

    def test_categories_keep_artistic_seniors_first(self):
        self.assertEqual(fe.categories(detail()), [('MAG', 'SR'), ('WAG', 'SR'), ('WAG', 'JR')])

    def test_unknown_supplier_is_blank(self):
        self.assertEqual(fe.suppliers(detail(apparatusSuppliers=[{'name': fe.UNKNOWN_SUPPLIER}])), '')

class DraftEventTest(unittest.TestCase):
    def test_rows_from_fig_record(self):
        rows = fe.draft_event_rows('2026-ASIAN-GAMES', [detail()])
        self.assertEqual([r['Prefix'] for r in rows], ['2026-ASIAN-GAMES-MAG-SR', '2026-ASIAN-GAMES-WAG-SR',
                                                       '2026-ASIAN-GAMES-WAG-JR'])
        r = rows[0]
        self.assertEqual(r['Slug'], '2026-asian-games-mag-sr')
        self.assertEqual(r['Title'], '20th Asian Games Aichi-Nagoya 2026')
        self.assertEqual(r['Short Name'], '')
        self.assertEqual(r['Level'], 'CONTINENTAL_GAMES')
        self.assertEqual((r['City'], r['Country'], r['FIG Event Number']), ('Nagoya', 'JPN', '18608'))

    def test_unmapped_level_left_blank(self):
        rows = fe.draft_event_rows('2026-X', [detail(level='World Age Group Competitions')])
        self.assertEqual({r['Level'] for r in rows}, {''})

    def test_regional_levels(self):
        self.assertEqual(fe.LEVELS['Commonwealth Games'], 'REGIONAL_GAMES')
        self.assertEqual(fe.LEVELS['Mediterranean Games'], 'REGIONAL_GAMES')
        self.assertEqual(fe.LEVELS['Other Regional Championships / Games'], 'REGIONAL_COMPETITION')

    def test_level_group(self):
        self.assertEqual(fe.level_group(detail(level={'name': 'x', 'group': 3}.get('name'))), '')
        d = detail()
        d['level'] = {'name': 'Commonwealth Games', 'group': 3}
        self.assertEqual(fe.level_group(d), 'Group 3')

    def test_two_events_covering_one_prefix_is_an_error(self):
        with self.assertRaises(SystemExit):
            fe.draft_event_rows('X', [detail(18565), detail(18567)])

class FolderTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = self.tmp.name
        self.patch = mock.patch.object(fe, 'year_dir', lambda year: self.root)
        self.patch.start()

    def tearDown(self):
        self.patch.stop()
        self.tmp.cleanup()

    def folder(self, name, *files):
        path = os.path.join(self.root, name)
        os.makedirs(path)
        for f in files:
            open(os.path.join(path, f), 'w').close()
        return path

    def test_fig_ids_from_pdf_json_and_event_csv(self):
        path = self.folder('2026-A', '18565-ResultsbookMedia.pdf', 'fig-18566.json')
        with open(os.path.join(path, '2026-A-EVENT.csv'), 'w', newline='') as f:
            w = csv.writer(f)
            w.writerow(['Prefix', 'FIG Event Number'])
            w.writerow(['2026-A-WAG-SR', '18567'])
        self.assertEqual(fe.folder_fig_ids(path), {18565, 18566, 18567})

    def test_folder_state(self):
        self.assertEqual(fe.folder_state(self.folder('e')), '')
        self.assertEqual(fe.folder_state(self.folder('d', '1-ResultsbookMedia.pdf')), 'Downloaded')
        self.assertEqual(fe.folder_state(self.folder('p', '1.pdf', 'X-MAG-SR-IMPORT.json')), 'Parsed')
        self.assertEqual(fe.folder_state(os.path.join(self.root, 'missing')), '')

    def write_event_csv(self, path, rows):
        with open(os.path.join(path, os.path.basename(path) + '-EVENT.csv'), 'w', newline='') as f:
            w = csv.writer(f)
            w.writerow(['Prefix', 'FIG Event Number'])
            w.writerows(rows)

    def test_event_state_per_fig_event(self):
        # Seniors parsed, juniors not yet downloaded: the 2026 African Championships.
        path = self.folder('2026-AF', '18377-ResultsbookMedia.pdf', '2026-AF-MAG-SR-IMPORT.json',
                           '2026-AF-WAG-SR-IMPORT.json')
        self.write_event_csv(path, [['2026-AF-MAG-SR', '18377'], ['2026-AF-WAG-SR', '18377']])
        self.assertEqual(fe.event_state(path, 18377), 'Parsed')
        self.assertEqual(fe.event_state(path, 18378), '')
        open(os.path.join(path, '18378-ResultsbookMedia.pdf'), 'w').close()
        self.assertEqual(fe.event_state(path, 18378), 'Downloaded')

    def test_event_state_where_pdfs_have_no_fig_id(self):
        path = self.folder('2026-EU', '2026-EU-MAG-RESULTS.pdf', '2026-EU-MAG-SR-IMPORT.json')
        self.write_event_csv(path, [['2026-EU-MAG-SR', '18235'], ['2026-EU-MAG-JR', '18236']])
        self.assertEqual(fe.event_state(path, 18235), 'Parsed')
        self.assertEqual(fe.event_state(path, 18236), 'Downloaded')

    def test_draft_event_csv_adds_missing_rows_only(self):
        path = self.folder('2026-AF')
        event_csv = os.path.join(path, '2026-AF-EVENT.csv')
        senior = detail(18377, disciplines=[{'code': 'MAG', 'agecategories': [{'name': 'Senior'}]}])
        junior = detail(18378, disciplines=[{'code': 'MAG', 'agecategories': [{'name': 'Junior'}, {'name': 'Senior'}]}])
        fe.draft_event_csv(event_csv, '2026-AF', [senior])
        with open(event_csv) as f:
            first = f.read()
        fe.draft_event_csv(event_csv, '2026-AF', [junior])
        _, rows = fe.read_csv(event_csv)
        self.assertEqual([(r['Prefix'], r['FIG Event Number']) for r in rows],
                         [('2026-AF-MAG-SR', '18377'), ('2026-AF-MAG-JR', '18378')])
        with open(event_csv) as f:
            self.assertTrue(f.read().startswith(first))

    def test_update_meets_takes_date_and_location_from_fig(self):
        link = 'https://www.gymnastics.sport/site/events/detail.php?id=18480&type=sport#loaded'
        rows = [{'Event': 'American Cup', 'Date': '2026-03-06', 'Location': 'Henderson, NV, USA',
                 'Status': '', 'FIG Event': link, 'Folder': ''},
                {'Event': 'Gymnix', 'Date': '2026-03-05', 'Location': 'Montreal, Quebec, CAN',
                 'Status': '', 'FIG Event': link.replace('18480', '18386'), 'Folder': ''}]
        vegas = detail(18480, startEvent='2026-03-07', city={'name': 'LAS VEGAS', 'country': {'code': 'USA'}})
        montreal = detail(18386, startEvent='2026-03-06', city={'name': 'MONTREAL', 'country': {'code': 'CAN'}})
        fe.update_meets(rows, {}, 2026, {18480: (vegas, None), 18386: (montreal, None)})
        self.assertEqual((rows[0]['Date'], rows[0]['Location']), ('2026-03-07', 'Las Vegas, USA'))
        self.assertEqual((rows[1]['Date'], rows[1]['Location']), ('2026-03-06', 'Montreal, Quebec, CAN'))

    def test_update_meets_fills_folder_and_derived_status_only(self):
        self.folder('2026-ASIAN-GAMES', '18608-book.pdf')
        self.folder('2026-WORLDS', '17247-ResultsbookMedia.pdf')
        link = 'https://www.gymnastics.sport/site/events/detail.php?id={}&type=sport#loaded'
        rows = [{'Event': 'Asian Games', 'Status': '', 'FIG Event': link.format(18608), 'Folder': ''},
                {'Event': 'Worlds', 'Status': 'Imported', 'FIG Event': link.format(17247), 'Folder': ''},
                {'Event': 'Nordics', 'Status': '', 'FIG Event': '', 'Folder': ''}]
        changes = fe.update_meets(rows, fe.fig_index(2026), 2026)
        self.assertEqual([(r['Folder'], r['Status']) for r in rows],
                         [('2026-ASIAN-GAMES', 'Downloaded'), ('2026-WORLDS', 'Imported'), ('', '')])
        self.assertEqual(len(changes), 3)

class MeetsListTest(unittest.TestCase):
    def test_header_names_fig_column_and_adds_folder(self):
        old = ['Date', 'Event', 'Location', 'Format', 'Disciplines', 'Organizer', 'Priority', 'Status',
               'Event Type', '', 'Results']
        new = fe.meets_header(old)
        self.assertEqual(new[9], 'FIG Event')
        self.assertEqual(new[-1], 'Folder')
        self.assertEqual(fe.meets_header(new), new)

    def test_add_link_skips_duplicates(self):
        row = {'Results': 'https://a'}
        fe.add_link(row, 'Results', 'https://a')
        fe.add_link(row, 'Results', 'https://b')
        self.assertEqual(row['Results'], 'https://a, https://b')

    def test_imported_holds_only_for_parsed_events(self):
        meet = {'Status': 'Imported'}
        self.assertEqual(fe.fig_event_status(meet, 'Parsed'), 'Imported')
        self.assertEqual(fe.fig_event_status(meet, ''), '')
        self.assertEqual(fe.fig_event_status({'Status': 'Cancelled'}, ''), 'Cancelled')
        self.assertEqual(fe.fig_event_status({'Status': 'Downloaded'}, 'Parsed'), 'Parsed')

    def test_sibling_folders(self):
        def row(i, start, end, folder='', city='Yaounde'):
            return {'FIG Event': i, 'Start Date': start, 'End Date': end, 'City': city, 'Folder': folder}
        senior = row(18377, '2026-04-21', '2026-04-27', '2026-AFRICAN-CHAMPIONSHIPS')
        junior = row(18378, '2026-04-23', '2026-04-26')
        elsewhere = row(1, '2026-04-23', '2026-04-26', 'X', city='Cairo')
        later = row(2, '2026-06-01', '2026-06-02', 'Y')
        self.assertEqual(fe.sibling_folders(junior, [senior, junior, elsewhere, later]),
                         ['2026-AFRICAN-CHAMPIONSHIPS'])

    def test_new_meet_row_goes_last_by_date(self):
        d = detail(18693, level='Continental Championships', startEvent='2026-11-05',
                   city={'name': 'AMMAN', 'country': {'code': 'JOR'}},
                   disciplines=[{'code': 'MAG', 'agecategories': [{'name': 'Junior'}]}])
        row = fe.new_meet_row('West Asia Championships', d)
        self.assertEqual((row['Location'], row['Disciplines'], row['Event Type']),
                         ('Amman, JOR', 'MAG Jr', 'Continental Championships'))
        self.assertEqual(fe.new_meet_row('x', detail(level='International Tournaments'))['Event Type'],
                         'International Invitational')
        rows = [{'Date': '2026-12-01', 'Priority': '1'}, {'Date': '2026-01-01', 'Priority': ''},
                {'Date': '2026-12-01', 'Priority': ''}]
        fe.insert_meet(rows, row)
        self.assertEqual([r['Date'] for r in rows], ['2026-12-01', '2026-01-01', '2026-11-05', '2026-12-01'])

    def test_candidates_match_city_within_a_week(self):
        fig = {'Start Date': '2026-03-07', 'City': 'Montreal'}
        meets = [{'Date': '2026-03-06', 'Event': 'Gymnix', 'Location': 'Montreal, Quebec, CAN'},
                 {'Date': '2026-05-06', 'Event': 'Later', 'Location': 'Montreal, Quebec, CAN'},
                 {'Date': '2026-03-07', 'Event': 'American Cup', 'Location': 'Henderson, NV, USA'}]
        self.assertEqual([m['Event'] for m in fe.candidates(fig, meets)], ['Gymnix'])

if __name__ == '__main__':
    unittest.main()
