
import os
import shutil
import tools.yamlSplit

versions = ["jp", "us"]

if __name__ == "__main__":
    if os.path.exists("split/"):
        shutil.rmtree("split/")

    anySplit = False
    for version in versions:
        # the call to `doSplit()` has to come first, otherwise once one split
        # succeeds, it will short-circuit and not evaluate `doSplit()` again
        anySplit = tools.yamlSplit.doSplit(version) or anySplit
    if not anySplit:
        raise(Exception("ERROR: did not find any ROM files to extract. Please put a clean\n"
              "MOTHER or Earthbound ROM in the same directory as configure.py"))
