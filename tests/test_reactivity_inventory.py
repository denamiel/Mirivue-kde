"""Work budgets and cache consistency, not machine-specific timing thresholds."""
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch
from PySide6.QtCore import Qt, QByteArray, QBuffer, QIODevice, QThread, Signal
from PySide6.QtGui import QAction, QPixmap
from PySide6.QtWidgets import QApplication
from mirivue.app import VideoModel, Window, FileSortProxy
from mirivue.metadata import Video, HEADERS


def video(number, complete=False):
    row=Video(Path('/inventaire')/f'film-{number}.mkv',is_video=True,media_type='video',metadata_loaded=True,is_hidden=False)
    row.values[0]=row.path.name;row.sort_values[0]=row.path.name
    if complete:
        row.media_technical={'width':1920,'height':1080}
        for column,value in [(2,60),(4,'h264'),(5,25),(6,1000)]:row.sort_values[column]=value
    return row

class CountingProxy(FileSortProxy):
    accepts_calls=0
    def filterAcceptsRow(self,*args):
        self.accepts_calls+=1
        return super().filterAcceptsRow(*args)

class ControlledThumbnailWorker(QThread):
    ready=Signal(object,object,object)
    def __init__(self,paths,force_paths=()):super().__init__()

class CountedRows(list):
    visits=0
    def __iter__(self):
        for row in super().__iter__():
            self.visits+=1
            yield row

class TestInventory(unittest.TestCase):
    @classmethod
    def setUpClass(cls):cls.app=QApplication.instance() or QApplication([])
    def model(self,n=100):
        model=VideoModel();model.add_preliminary([video(i) for i in range(n)])
        return model
    def test_path_index_tracks_insert_replace_remove_reset_and_rename(self):
        model=self.model(4)
        self.assertEqual(model.positions_for_path(video(3).path),(3,))
        old=model.rows[2].path;model.rows[2].path=Path('/inventaire/renomme.mkv')
        model.dataChanged.emit(model.index(2,0),model.index(2,len(HEADERS)-1))
        self.assertEqual(model.positions_for_path(old),())
        self.assertEqual(model.positions_for_path(model.rows[2].path),(2,))
        model.remove_paths([model.rows[0].path,model.rows[1].path])
        self.assertEqual(model.positions_for_path(video(3).path),(1,))
        model.beginResetModel();model.rows=[video(8)];model.endResetModel()
        self.assertEqual(model.positions_for_path(video(3).path),())
        self.assertEqual(model.positions_for_path(video(8).path),(0,))
        model.clear();self.assertEqual(model.positions_for_path(video(8).path),())
    def test_preliminary_replacement_and_duplicate_paths_stay_consistent(self):
        model=self.model(1);path=model.rows[0].path
        model.preliminary[path]=0
        with patch('mirivue.app.update_modification'),patch('mirivue.media.sync_columns'):
            model.add(video(0,True))
        self.assertEqual(model.positions_for_path(path),(0,));self.assertEqual(model.incomplete_count,0)
        model.add_preliminary([video(0)])
        self.assertEqual(model.positions_for_path(path),(0,1));self.assertEqual(model.incomplete_count,1)
        model.remove_paths([path]);self.assertEqual(model.incomplete_count,0)
    def test_counter_updates_on_metadata_changes_and_ignores_decoration(self):
        model=self.model(3);self.assertEqual(model.incomplete_count,3)
        model.rows[1]=video(1,True)
        model.dataChanged.emit(model.index(1,0),model.index(1,len(HEADERS)-1),[Qt.DisplayRole])
        self.assertEqual(model.incomplete_count,2)
        with patch('mirivue.app.media_missing_fields',side_effect=AssertionError('thumbnail must not recount')):
            model.dataChanged.emit(model.index(0,0),model.index(2,0),[Qt.DecorationRole])
            self.assertEqual(model.incomplete_count,2)
        model.remove_paths([video(0).path]);self.assertEqual(model.incomplete_count,1)
        model.beginResetModel();model.rows=[video(5,True)];model.endResetModel()
        self.assertEqual(model.incomplete_count,0)
    def test_selection_does_not_rescan_all_media(self):
        model=self.model()
        owner=SimpleNamespace(model=model,scanning=False,is_archive_view=lambda:False,selected_indexes=lambda:[],
            update_selection_info=Mock(),duplicate_action=QAction(),keep_one_action=QAction(),
            duplicate_groups=[],refresh_delete_availability=Mock(),incomplete_media_action=QAction())
        Window.update_delete_button(owner)
        with patch('mirivue.app.media_missing_fields',wraps=__import__('mirivue.app',fromlist=['media_missing_fields']).media_missing_fields) as predicate:
            for _ in range(10):Window.update_delete_button(owner)
        self.assertEqual(predicate.call_count,0)
    def test_duration_result_visits_only_its_row(self):
        model=self.model();path=model.rows[-1].path
        if hasattr(model,'positions_for_path'):model.positions_for_path(path)
        model.rows=CountedRows(model.rows)
        with patch('mirivue.app.fingerprint',return_value=(1,2,3)):
            Window.apply_quick_metadata(SimpleNamespace(model=model),path,(1,2,3),{'duration':42})
        self.assertEqual(model.rows[-1].sort_values[2],42)
        self.assertEqual(model.rows.visits,0)
    def test_thumbnail_result_visits_only_matching_rows(self):
        model=self.model();path=model.rows[-1].path
        if hasattr(model,'positions_for_path'):model.positions_for_path(path)
        model.rows=CountedRows(model.rows)
        pixmap=QPixmap(2,2);pixmap.fill(Qt.red);data=QByteArray();buffer=QBuffer(data);buffer.open(QIODevice.WriteOnly);pixmap.save(buffer,'PNG')
        with patch('mirivue.app.fingerprint',return_value=(1,2,3)):
            Window.thumbnail_ready(SimpleNamespace(model=model),path,(1,2,3),bytes(data))
        self.assertIn(path,model.thumbnails);self.assertEqual(model.rows.visits,0)
    def test_stale_results_do_not_change_the_model(self):
        model=self.model(2)
        with patch('mirivue.app.fingerprint',return_value=(9,9,9)):
            Window.apply_quick_metadata(SimpleNamespace(model=model),model.rows[0].path,(1,2,3),{'duration':42})
        self.assertEqual(model.rows[0].sort_values[2],-1)

class TestFilterChanges(unittest.TestCase):
    @classmethod
    def setUpClass(cls):cls.app=QApplication.instance() or QApplication([])
    def test_name_filter_changes_only_when_needed(self):
        model=VideoModel();model.add_preliminary([video(1),video(2)])
        proxy=CountingProxy();proxy.setSourceModel(model);proxy.rowCount()
        proxy.set_name_filter('film-1');self.assertEqual(proxy.rowCount(),1)
        self.assertGreater(proxy.accepts_calls,0);proxy.accepts_calls=0
        for _ in range(10):proxy.set_name_filter('film-1');proxy.rowCount()
        self.assertEqual(proxy.accepts_calls,0)
        proxy.set_name_filter('film-2');self.assertEqual(proxy.index(0,0).data(),'film-2.mkv')
    def test_legacy_qt_fallback_keeps_filtering_correct(self):
        model=VideoModel();model.add_preliminary([video(1),video(2)])
        proxy=FileSortProxy();proxy.setSourceModel(model)
        with patch.object(FileSortProxy,'endFilterChange',None):
            proxy.set_name_filter('film-2')
        self.assertEqual(proxy.rowCount(),1);self.assertEqual(proxy.index(0,0).data(),'film-2.mkv')

import test_pane_regressions_gui as pane_fixture

class TestBackgroundResults(unittest.TestCase):
    @classmethod
    def setUpClass(cls):cls.app=QApplication.instance() or QApplication([])
    def setUp(self):
        with patch('mirivue.app.FileSortProxy',CountingProxy):
            pane_fixture.TestPaneRegressions.setUp(self)
    tearDown=pane_fixture.TestPaneRegressions.tearDown
    drain=pane_fixture.TestPaneRegressions.drain
    def exercise(self, thumbnail):
        w=self.window;left,right=w.panes
        for pane in (left,right):
            w.activate_pane(pane);pane.model.clear()
            pane.model.add_preliminary([video(i) for i in range(128)])
            w.quick_filter.setText('film');w.capture_pane();pane.proxy.rowCount()
        if thumbnail:
            w.activate_pane(right);right.model.show_thumbnails=True
            with patch('mirivue.app.ThumbnailWorker',ControlledThumbnailWorker),patch.object(w,'start_runtime_worker'):
                w.start_thumbnails()
            thumbnail_worker=w.thumbnail_worker
            w.capture_pane()
        w.activate_pane(left);left.proxy.rowCount();right.proxy.rowCount();self.drain()
        left.proxy.invalidateFilter();left.proxy.rowCount()
        self.assertGreater(left.proxy.accepts_calls,0)
        left.proxy.accepts_calls=right.proxy.accepts_calls=0
        path=right.model.rows[-1].path
        with patch('mirivue.app.fingerprint',return_value=(1,2,3)):
            if thumbnail:
                pixmap=QPixmap(2,2);pixmap.fill(Qt.red);data=QByteArray();buffer=QBuffer(data);buffer.open(QIODevice.WriteOnly);pixmap.save(buffer,'PNG')
                thumbnail_worker.ready.emit(path,(1,2,3),bytes(data))
            else:
                w.run_in_pane_silent(right,w.apply_quick_metadata,path,(1,2,3),{'duration':42})
            left.proxy.rowCount();right.proxy.rowCount();self.drain()
        self.assertIs(w.bound_pane,left)
        print(f'\nRésultat {"miniature" if thumbnail else "durée"} : filtre gauche={left.proxy.accepts_calls}, droit={right.proxy.accepts_calls}')
        self.assertEqual(left.proxy.accepts_calls,0)
        self.assertLess(right.proxy.accepts_calls,10)
        if thumbnail:self.assertIn(path,right.model.thumbnails)
        else:self.assertEqual(right.model.rows[-1].sort_values[2],42)
    def test_background_duration_does_not_refilter_the_other_panel(self):self.exercise(False)
    def test_background_thumbnail_does_not_refilter_the_other_panel(self):self.exercise(True)
