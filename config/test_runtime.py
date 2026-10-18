import sqlite3
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch
from django.test import SimpleTestCase
import runtime

class RuntimeIsolationTests(SimpleTestCase):
    def test_clone_is_independent_and_refuses_overwrite(self):
        with TemporaryDirectory(dir=runtime.PRIVATE) as temp:
            source=Path(temp)/'live.sqlite3'; target=Path(temp)/'dev.sqlite3'
            with sqlite3.connect(source) as db:
                db.execute('create table actions (title text)')
                db.execute("insert into actions values ('live')")
            db.close()
            runtime.clone_database(source,target)
            with sqlite3.connect(target) as db:
                db.execute("update actions set title='development'")
            db.close()
            with sqlite3.connect(source) as db:
                self.assertEqual(db.execute('select title from actions').fetchone()[0],'live')
            db.close()
            with self.assertRaises(ValueError): runtime.clone_database(source,target)

    def test_release_is_independent_and_path_is_confined(self):
        with TemporaryDirectory(dir=runtime.PRIVATE) as temp:
            root=Path(temp); (root/'config').mkdir(); (root/'config'/'settings.py').write_text('first')
            (root/'manage.py').write_text('entry')
            with patch.multiple(runtime,ROOT=root,PRIVATE=root/'private',SOURCE_DIRS=('config',),SOURCE_FILES=('manage.py',)):
                release=runtime.prepare_release()
                (root/'config'/'settings.py').write_text('changed')
                self.assertEqual((release/'config'/'settings.py').read_text(),'first')
                self.assertEqual(runtime.release_path(),release)
                (root/'private'/'release-next.txt').write_text('../escape')
                with self.assertRaises(ValueError):runtime.release_path()
