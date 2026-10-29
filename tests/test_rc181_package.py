"""Execute package() into a disposable staging tree and inspect archive bytes."""
import os,subprocess,tarfile,tempfile,unittest
from pathlib import Path
import mirivue

class TestReleaseLicenses(unittest.TestCase):
 def test_archive_and_real_package_contain_all_license_provenance_files(self):
  root=Path(mirivue.__file__).resolve().parents[1]
  library=os.environ.get('MIRIVUE_TEST_DOLPHIN_LIBRARY','')
  self.assertTrue(Path(library).is_file(),'Compile the native release helpers before running this test')
  expected=['LICENSE','LICENSES/GPL-3.0-or-later.txt','LICENSES/MIT.txt','LICENCES-TIERS.md','native/NATURAL-SORT-UPSTREAM.json','native/DATE-GROUPS-UPSTREAM.json','native/dolphin-engine/UPSTREAM.json','native/dolphin-engine/README.md','mirivue/servicemenu.knsrc']
  with tempfile.TemporaryDirectory(prefix='mirivue-release-licenses-') as d:
   work=Path(d);archive=work/'release.tar.gz'
   with tarfile.open(archive,'w:gz') as tar:
    for name in expected:tar.add(root/name,arcname=root.name+'/'+name)
   with tarfile.open(archive) as tar:
    for name in expected:self.assertEqual(tar.extractfile(root.name+'/'+name).read(),(root/name).read_bytes())
   source=work/'src';source.mkdir();(source/root.name).symlink_to(root,target_is_directory=True);(source/'build').symlink_to(Path(library).parent,target_is_directory=True)
   package=work/'pkg';package.mkdir()
   script='set -e\nsource "$1"\nsrcdir="$2"\npkgdir="$3"\npackage\n'
   result=subprocess.run(['bash','-c',script,'audit-package',str(root/'packaging/PKGBUILD.template'),str(source),str(package)],capture_output=True,text=True,timeout=30)
   self.assertEqual(result.returncode,0,result.stderr)
   licenses=package/'usr/share/licenses/mirivue-kde'
   for name in ('LICENSE','LICENSES/GPL-3.0-or-later.txt','LICENSES/MIT.txt','LICENCES-TIERS.md','NATURAL-SORT-UPSTREAM.json','DATE-GROUPS-UPSTREAM.json','dolphin-engine/UPSTREAM.json','dolphin-engine/README.md'):
    self.assertTrue((licenses/name).is_file(),name)
   self.assertEqual((licenses/'LICENSES/GPL-3.0-or-later.txt').read_bytes(),(root/'LICENSES/GPL-3.0-or-later.txt').read_bytes())
   self.assertTrue((package/'usr/lib/mirivue-kde/mirivue/servicemenu.knsrc').is_file())
   self.assertFalse(list((package/'usr/lib/mirivue-kde/tools').glob('*test*')))
if __name__=='__main__':unittest.main(verbosity=2)
