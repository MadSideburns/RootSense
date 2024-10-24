from loguru import logger
from pathlib import Path
from rootsense_classes import RSTree
import time
import subprocess

def timed(f, *args):
    '''
    Times the execution of the function f

    Returns
    -------
    tuple: `(f(*args), exec_time)`
    '''
    t0 = time.time()
    result = f(*args)
    return (result, time.time() - t0)

def bash_command(command):
    '''
    Runs the `command` on the system bash

    Parameters
    ----------
    command: str
        The command you want to run

    Returns
    -------
    `subprocess.CompletedProcess` object containing the result of the command, as text with output captured
    '''
    #split the command to conform to the run routine syntax
    base_command = command.split()[0]
    options = command.replace(base_command + ' ', '')
    
    return subprocess.run([base_command, options], capture_output=True, text=True)

def main():
    #some system paths where to locate included files
    sys_include_paths = [Path(p) for p in ['/usr/include', '/usr/local/include', '/usr/lib', '/lib/modules']]

    #gather start time
    start_time = time.time()

    logger.info('Gathering root install path...')
    #this generates something like '/home/{user}/root/bin/root'
    root_exec_path_result = bash_command('which root')
    if root_exec_path_result.returncode != 0:
        raise OSError('Root installation not found. Make sure root is installed and set in your PATH variable.')

    root_exec_path = Path(root_exec_path_result.stdout)
    #this will be the root base folder '/home/{user}/root'
    root_base_path = root_exec_path.parents[1]
    root_include_path = root_base_path / 'include'
    logger.info(f'Found root include path {root_include_path}')

    logger.info(f'Generating file trees. This may take a while...')
    root_tree, root_time = timed(RSTree.from_dir, root_include_path)
    print(root_tree['TH1Feee.h'])
    logger.success(f'root tree created in {root_time} seconds: {root_tree.size()} elements with depth {root_tree.depth()}')
    

    sys_tree, sys_time = timed(RSTree.from_dir, *sys_include_paths)
    logger.success(f'sys tree created in {sys_time} seconds: {sys_tree.size()} elements with depth {sys_tree.depth()}')


if __name__ == '__main__':
    main()