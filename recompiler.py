import tools.ios.DialogueIO as DialogueIO
import tools.ios.TextPointerIO as TextPointerIO
import yaml
import os
import shutil
from glob import glob
import hashlib

FILL_BYTE = 0xff

def get_rom_pos(memfile):
    HEADER_START = 0x0
    HEADER_END = HEADER_START+0x10
    PRG_START = HEADER_END
    PRG_END = PRG_START+(0x20*0x2000)
    CHR_START = PRG_END
    CHR_END = CHR_START+(0x20*0x2000)

    addr = 0
    if memfile["type"] == "CHR":
        addr = CHR_START
    else:
        addr = PRG_START

    return addr + (memfile["bank"]*0x2000) + memfile["pos"]


if __name__ == "__main__":
    shutil.rmtree("recompile/")
    os.makedirs("recompile/us/")

    dir = "us"
    yamlname = dir+".yaml"
    if not os.path.exists(yamlname):
        print("yaml does not exist! skipping...")
        exit()
    data_loaded = yaml.safe_load(open(yamlname, 'r'))

    rom = ""
    for mrom in glob("*.nes"):
        hash = hashlib.md5(open(mrom,'rb').read()).hexdigest()
        for expect_hash in data_loaded["md5"]:
            if hash == expect_hash:
                rom = mrom
                break
    if rom == "":
        exit()

    rom_bytes = bytearray(open(rom, "rb").read())

    memory = yaml.safe_load(open("config/us/memory.yaml", "r"))

    x = 0
    while x < 10:
        file = f"dialogue{x+1}"

        byte_data, pointers = DialogueIO.compile(open(f"extract/us/{file}.asm", "r").read())

        open(f"recompile/us/{file}.bin", "wb").write(byte_data)
        pointers = [[value, key] for key, value in pointers.items()]

        pointers = yaml.safe_dump({file: pointers}, None,
                    default_flow_style=None,
                    sort_keys=False)
        open(f"recompile/us/{file}.ptr", "w").write(pointers)

        #dialogue
        memfile = memory[file]
        pos_start = get_rom_pos(memfile)
        free_length = memfile["size"]
        pos_end = pos_start+free_length
        rom_bytes[pos_start:pos_end] = bytearray([FILL_BYTE] * free_length)
        if len(byte_data) > free_length:
            print(f"""
                text_pointer data is too big!
                0x{len(byte_data):0X} is too big for 0x{free_length:0X}
                """)
            exit()

        pos_end = pos_start+len(byte_data)
        rom_bytes[pos_start:pos_end] = byte_data

        x += 1

    res = TextPointerIO.compile(open("extract/us/text_pointers.asm", "r").read())
    open("recompile/us/text_pointers.bin", "wb").write(res)

    memfile = memory["text_pointers"]
    pos_start = get_rom_pos(memfile)
    free_length = memfile['size']
    pos_end = pos_start+free_length
    rom_bytes[pos_start:pos_end] = bytearray([FILL_BYTE] * free_length)
    if len(res) > free_length:
        print(f"""
               text_pointer data is too big!
               0x{len(res):0X} is too big for 0x{free_length:0X}
               """)
        exit()
    pos_end = pos_start+len(res)
    rom_bytes[pos_start:pos_end] = res

    open("mother_rebuilt.nes", "wb").write(rom_bytes)