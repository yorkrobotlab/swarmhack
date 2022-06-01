#!/bin/bash

page=1
tags_per_page=5

# 30 unique Pi-puck IDs
for i in {1..30}
do
    echo $i, $page

    python3 generate_tag.py --id $i --diameter 70

    if [ $((i % tags_per_page)) -eq 0 ]
    then
        montage -geometry +2+2 DICT_* $page.png
        ((page++))
        rm -rf DICT_*
    fi
done

# 30 unique MONA IDs
for i in {31..60}
do
    echo $i, $page

    python3 generate_tag.py --id $i --diameter 80

    if [ $((i % tags_per_page)) -eq 0 ]
    then
        montage -geometry +2+2 DICT_* $page.png
        ((page++))
        rm -rf DICT_*
    fi
done