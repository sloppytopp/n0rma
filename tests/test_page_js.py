import os
import re
import shutil
import subprocess
import tempfile
import unittest

from n0rma import web


@unittest.skipUnless(shutil.which("node"), "node not installed")
class PageJsTest(unittest.TestCase):
    def test_dashboard_script_parses(self):
        js = re.search(r"<script>(.*)</script>", web.PAGE, re.S).group(1)
        with tempfile.TemporaryDirectory() as d:
            p = os.path.join(d, "page.js")
            open(p, "w").write(js)
            r = subprocess.run(["node", "--check", p], capture_output=True, text=True)
        self.assertEqual(r.returncode, 0, r.stderr)

    def test_radar_cards_wording(self):
        js = re.search(r"<script>(.*)</script>", web.PAGE, re.S).group(1)
        a, b = js.index("function rssiToM"), js.index("function blips")
        c, e = js.index("function rband"), js.index("function drawMini")
        prog = js[a:b] + js[c:e] + """
const d={my_ssids:['Home'],wifi_mine:[],live:{wifi:[{ssid:'Home',bssid:'aa:bb:cc:dd:ee:01',signal:-40,vendor:'x',klass:'other'},
{ssid:'(hidden)',bssid:'e0:b2:60:41:b1:79',signal:-55,vendor:'x',klass:'other'}],ble:{trackers:[]}}};
console.log(JSON.stringify(rcItems(d).map(i=>[i.title,i.col,i.fl])));"""
        r = subprocess.run(["node", "-e", prog], capture_output=True, text=True)
        self.assertEqual(r.stdout.strip(), '[["Home","good",false],["(hidden)","watch",true]]', r.stderr)


if __name__ == "__main__":
    unittest.main()
