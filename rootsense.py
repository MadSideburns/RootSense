from loguru import logger
from pathlib import Path
import os
import subprocess
import argparse

def run_command(command, target='stdout'):
    '''
    Runs the `command` on the system bash

    Parameters
    ----------
    command: str
        The command you want to run
    target: str, default='stdout'
        Defines wether to return the command output on `stdout`, `stderr`, or return directly the `subprocess.CompletedProcess` object
    '''
    #split the command to conform to the run routine syntax
    base_command = command.split()[0]
    options = command.replace(base_command + ' ', '')
    
    command_result = subprocess.run([base_command, options], capture_output=True, text=True)
    if target == 'obj':
        return command_result
    elif target == 'stdout':
        return command_result.stdout
    elif target == 'stderr':
        return command_result.stderr

def main(args):
    logger.info('Gathering root install path...')
    #this generates something like '/home/{user}/root/bin/root'
    root_exec_path_result = run_command('which root', 'obj')
    if root_exec_path_result.returncode != 0:
        raise OSError('Root installation not found. Make sure root is installed and set in your PATH variable')

    root_exec_path = Path(root_exec_path_result.stdout)
    #this will be the root base folder '/home/{user}/root'
    root_base_folder = root_exec_path.parents[1]
    logger.info(f'Found root base folder {root_base_folder}')
    
    #now we need to navigate to the include path
    root_include_folder = root_base_folder / 'include'

    #get all the '*.h' files in this folder
    include_files = list(root_include_folder.glob('*.h'))
    logger.info(f'{len(include_files)} header files found in {root_include_folder}')
    
    for file in include_files:
        print(file)


if __name__ == '__main__':
    prog_description = 'Generate a header file including all root libraries'
    parser = argparse.ArgumentParser(description=prog_description, formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    parser.add_argument('-d', '--dir', default=None, help='Specify the directory where root is installed')
    args = parser.parse_args()

    main(args)