import yaml

write_over = {}

fuck = open(f"//wsl.localhost/Ubuntu/root/mother/linked.txt", "r").readlines()

symbols = {}
i = 0
while i < len(fuck):
    line = fuck[i].strip()
    args = line.split(" ")
    name = args[2][1:]
    addr = int(args[1], 16)
    symbols[name] = addr
    i += 1

x = 0
while x < 10:
    choose_file = f"dialogue{x+1}"
    file = open(f"//wsl.localhost/Ubuntu/root/mother/src/us/text/{choose_file}.asm", "r").readlines()

    labels = []

    i = 0
    while i < len(file):
        line = file[i].strip()

        if line.endswith(":") and line.startswith("MSG_"):
            labels.append(line[:-1])

        i += 1

    write_over[choose_file] = []

    i = 0
    while i < len(labels):
        chosen_label = labels[i]
        entry = [symbols[chosen_label]-(x*0x2000), chosen_label]
        write_over[choose_file].append(entry)
        i += 1

    x += 1

def to_hexer(dumper, data):
    return dumper.represent_scalar('tag:yaml.org,2002:str', hex(data))

yaml.SafeDumper.add_representer(int, to_hexer)
write_over = yaml.safe_dump(write_over, None,
               default_flow_style=None,
               sort_keys=False).replace("['", "[").replace("',", ",")
open("config/us/newlabels.yaml", "w").writelines(write_over)