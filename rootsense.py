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

def write_files(file, base_folder, relative_path):
    excluded_files = ['AllRoot.h', 'rootsense.h']

    #compute the working folder
    working_folder = base_folder / relative_path

    #gather all subfolders of the working folder
    subfolders = [folder.name for folder in working_folder.iterdir() if folder.is_dir()]
    for subfolder in subfolders:
        #recursively call this function on all subfolders
        write_files(file, base_folder, relative_path + f'{subfolder}/')

    #get all the '*.h' and '*.hh' files in this folder
    header_files_paths = [file for file in working_folder.glob('*') if file.suffix in ['.h', '.hh']]
    header_files_names = [filepath.name for filepath in header_files_paths if filepath.name not in excluded_files]
    logger.info(f'{len(header_files_names)} header files found in {working_folder}')
    for name in header_files_names:
        file.write(f'#include \"{relative_path + name}\"\n')

    #get all the subfolders

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

    #open target file
    include_all_file = Path(root_include_folder, 'rootsense.h')
    with include_all_file.open('w') as file:
        logger.info(f'Writing include directives in {include_all_file}...')
        file.write('#ifndef ROOTSENSE\n')
        file.write('#define ROOTSENSE\n\n')
        write_files(file, root_include_folder, '')
        file.write('\n#endif')

    


if __name__ == '__main__':
    prog_description = 'Generate a header file including all root libraries'
    parser = argparse.ArgumentParser(description=prog_description, formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    parser.add_argument('-d', '--dir', default=None, help='Specify the directory where root is installed')
    args = parser.parse_args()

    main(args)