#!/bin/bash

python3 generate_tag.py --id 0 --diameter 100
montage -geometry +2+2 DICT_4X4_100_0.png DICT_4X4_100_0.png DICT_4X4_100_0.png DICT_4X4_100_0.png corners.png
