import numpy as np
from PIL import Image
import yaml

class Tile16(object):
    def __init__(self, tilesGiven, tileNumGiven):
        self.tiles = tilesGiven
        self.tileNumGiven = tileNumGiven

class Tile64(object):
    def __init__(self, tile16_is, palette64_i, alt_tiles, tilenums):
        self.tile16_is = tile16_is
        self.palette64_i = palette64_i
        self.alt_tiles = alt_tiles
        self.tilenums = tilenums

class MapInfo(object):
    def __init__(self, in_type):
        if type(in_type) == bytes:
            self.decompile(in_type)

    def decompile(self, byte_data):
        #Map height * width in terms of 64x64 chunks
        mapTiles = []
        mapTileset = [] #second tileset
        mapEvent = []

        #Same as above, divided by 4
        sectorPalette = []
        sectorArea = []
        sectorTileset1 = []
        sectorTileset2 = []

        banksMap = [0x2000, 0x6000, 0xA000, 0xE000, 0x12000, 0x16000, 0x1A000]
        curBank = 0
        for offset in banksMap:
            for i in range(0x2000):
                currentByte = byte_data[offset + i]
                mapTiles.append(currentByte & 0b00111111); #Get lower 6 bits only of map data, store in array
                mapTileset.append((currentByte & 0b01000000) != 0)
                mapEvent.append((currentByte & 0b10000000) != 0)
            curBank += 1

        #Lower 6 bits of 3800-3FFF (skip 1st bank)
        banksSector = [0x5800, 0x9800, 0xD800, 0x11800, 0x15800, 0x19800, 0x1D800]
        curBank = 0
        for offset in banksSector:
            for i in range(0x200):
                tileOffs = offset + (i * 4) #Offset of current 256x256 sector data
                #First 6 bits of each byte
                sectorPalette.append(byte_data[tileOffs] & 0b00111111)
                sectorArea.append(byte_data[tileOffs+1] & 0b00111111)
                sectorTileset1.append(byte_data[tileOffs+2] & 0b00111111)
                sectorTileset2.append(byte_data[tileOffs+3] & 0b00111111)
            curBank += 1

        #Lower 6 bits of 3000-37FF
        graphics16 = []
        banks16 = [0x1000, 0x5000, 0x9000, 0xD000, 0x11000, 0x15000, 0x19000, 0x1D000]
        palettes64 = []
        curBank = 0
        for offset in banks16:
            for i in range(0x200):
                tileset = (curBank * 4) + (i // 0x80) #4 tilesets for each bank
                tileset *= 64
                tileOffs = offset + (i * 4) #Offset of current 16x16 tile data
                graphics16.append(Tile16([
                    tileset + (  byte_data[tileOffs] & 0b00111111),
                    tileset + (byte_data[tileOffs+1] & 0b00111111),
                    tileset + (byte_data[tileOffs+2] & 0b00111111),
                    tileset + (byte_data[tileOffs+3] & 0b00111111),
                    ],
                    i & 0b01111111
                ))
            for i in range(0x100):
                paletteOffs = offset + (i * 0x10); #Offset of current 64x64 palette data
                new_palette = []
                for j in range(0x10):
                    value = (byte_data[paletteOffs + j] & 0b11000000) >> 6
                    new_palette.append(value)
                palettes64.append(new_palette)
            curBank += 1

        #2000-2FFF
        banks64 = [0, 0x4000, 0x8000, 0xC000, 0x10000, 0x14000, 0x18000, 0x1C000]
        graphics64 = []
        curBank = 0
        for offset in banks64:
            for i in range(0x100):
                tileset = (curBank * 4) + (i // 64); #4 tilesets for each bank
                tileOffs = offset + (i * 16); #Offset of current 64x64 palette data
                curTiles = [] #Tile16's
                altTileset = []
                tileNums = []

                #Iterate through the 64x64 tile data & decode it
                for j in range(0x10):
                    subOffs = tileOffs + j
                    tileNum = byte_data[subOffs] & 0b01111111
                    #This gets the correct 16x16 tile from the loaded list (ignoring all that alternate tileset crap)
                    curTiles.append((tileset * 128) + tileNum)
                    tileNums.append(tileNum)

                    if (byte_data[subOffs] & 0b10000000): #If last bit is set, use alternate tileset
                        altTileset.append(j)

                graphics64.append(Tile64(curTiles, (curBank*0x100)+i, altTileset, tileNums))
            curBank += 1

        self.g64 = graphics64
        self.g16 = graphics16

        self.mapTiles = mapTiles
        self.mapTileset = mapTileset
        self.mapEvent = mapEvent

        self.sectorPalette = sectorPalette
        self.sectorArea = sectorArea
        self.sectorTileset1 = sectorTileset1
        self.sectorTileset2 = sectorTileset2

        self.palette64 = palettes64




map = MapInfo(open("split/map.bin", "rb").read())

test = yaml.dump(map, sort_keys=False, default_flow_style=True)
open("map.yaml", "w").writelines(test)