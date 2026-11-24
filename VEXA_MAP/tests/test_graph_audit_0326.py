import importlib.util
import sqlite3
import tempfile
import unittest
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / 'tools' / 'audit_navigation_graph.py'
spec = importlib.util.spec_from_file_location('audit_navigation_graph', SCRIPT)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)

class GraphAuditTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.path = Path(self.temp.name) / 'test.mbtiles'
        with sqlite3.connect(self.path) as db:
            db.executescript('''CREATE TABLE metadata(name TEXT,value TEXT);
                CREATE TABLE vexa_nodes(node_id INTEGER PRIMARY KEY,latitude REAL,longitude REAL);
                CREATE TABLE vexa_edges(source_id INTEGER,target_id INTEGER,distance_m REAL,duration_s REAL);
                INSERT INTO metadata VALUES('vexa_navigation_schema','v1');
                INSERT INTO metadata VALUES('vexa_region_id','central');
                INSERT INTO vexa_nodes VALUES(1,55.75,37.61),(2,55.76,37.62);
                INSERT INTO vexa_edges VALUES(1,2,200,20);''')
    def tearDown(self): self.temp.cleanup()
    def test_valid(self):
        result = module.audit(self.path, 'central')
        self.assertTrue(result['ok'])
        self.assertEqual(result['directed_edges'], 1)
    def test_wrong_region(self): self.assertFalse(module.audit(self.path, 'ural')['ok'])
    def test_broken_edge(self):
        with sqlite3.connect(self.path) as db: db.execute('INSERT INTO vexa_edges VALUES(2,999,100,10)')
        self.assertIn('edges referencing missing nodes', module.audit(self.path)['errors'])
    def test_invalid_weight(self):
        with sqlite3.connect(self.path) as db: db.execute('INSERT INTO vexa_edges VALUES(2,1,-1,5)')
        self.assertIn('invalid edge weights', module.audit(self.path)['errors'])
    def test_readonly(self):
        before = self.path.read_bytes()
        module.audit(self.path)
        self.assertEqual(before, self.path.read_bytes())

if __name__ == '__main__': unittest.main()

