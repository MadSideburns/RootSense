from loguru import logger
from pathlib import Path
from rootsense_utils import RSNode, ProgressBar, bash_command, timed
import time
import subprocess

def main():
    #some system paths where to locate included files
    """ sys_include_paths = ['/usr/include', '/usr/local/include', '/usr/lib', '/lib/modules'] """
    sys_include_paths = ['/usr/modules', '/usr/include']
    sys_include_paths = [Path(p) for p in sys_include_paths]

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

    #generate root tree
    logger.info(f'Generating file trees. This may take a while...')
    root_tree, root_time = timed(RSNode.from_dir, root_include_path, progress=True)
    logger.success(f'root tree created in {root_time} seconds: {root_tree.size()} elements with depth {root_tree.depth()}')
    
    #generate system tree
    sys_tree, sys_time = timed(RSNode.from_dir, *sys_include_paths, progress=True)
    logger.success(f'sys tree created in {sys_time} seconds: {sys_tree.size()} elements with depth {sys_tree.depth()}')

    generate_rootsense(root_include_path, [root_tree, sys_tree])
    
def generate_rootsense(include_path, trees):
    #this tree is the merger of all the others
    global_tree = RSNode.merge(*trees)
    global_tree.printout()

    #find all header files in root's include path
    include_files = include_path.rglob('*')
    include_files = [file for file in include_files if file.is_file() and file.suffix in ['.h', '.hh']]
    
    #this list will contain all files to be included in rootsense.h
    files_to_be_written = []
    #this set will contain all paths which will need to be added to VScode's include paths
    VS_includes = set()

    bar = ProgressBar()
    n = len(include_files)
    logger.info(f'Parsing {n} header files found in {include_path}...')
    bar.initialize()
    for i, file in enumerate(include_files):
        bar.update(i/n)
        if global_tree.get_seen_status(file):
            continue
        if True:
            global_tree.mark_as_seen(file)
            files_to_be_written.append(str(file))
    bar.terminate()

if __name__ == '__main__':
    main()