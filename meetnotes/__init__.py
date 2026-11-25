import sys

# soundcard and uiautomation (via comtypes) both use COM. Use the multithreaded apartment
# everywhere so they don't conflict ("Cannot change thread mode after it is set").
# Must be set before comtypes is imported.
sys.coinit_flags = 0
