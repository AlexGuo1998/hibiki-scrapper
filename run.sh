#!/usr/bin/env bash

source "$HOME/.bashrc"
#conda activate
#cd "$HOME/hibiki/" || exit
export PYTHONUNBUFFERED=1
python main.py 1>>out.log 2>&1
