import tools.ios.DialogueIO as DialogueIO
import tools.ios.TextPointerIO as TextPointerIO
import os
import shutil

if __name__ == "__main__":
    shutil.rmtree("extract/")
    os.makedirs("extract/us/")

    x = 0
    while x < 10:
        file = f"dialogue{x+1}"

        res = DialogueIO.decompile(open(f"split/us/{file}.bin", "rb").read(), file)
        open(f"extract/us/{file}.asm", "w").write(res)
        x += 1

    res = TextPointerIO.decompile(open("split/us/text_pointers.bin", "rb").read())
    open("extract/us/text_pointers.asm", "w").writelines(res)