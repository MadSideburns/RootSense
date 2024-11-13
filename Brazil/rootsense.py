from loguru import logger
from dataclasses import dataclass, field
from pathlib import Path
import subprocess
import argparse
import sys
import time

#simple global variable to keep track of the number of lines written on the output file
out_lines = 0

class ProgressBar:
    def __init__(self, frac: float = 0.0, bar_length: int = 50):
        self.frac = frac
        self.bar_length = bar_length


    def update(self, frac = None):
        #updates the progress bar and prints it in place
        if frac is not None:
            self.frac = frac
        

        fill_width = int(self.frac * self.bar_length)
        bar = '#' * fill_width + '-' * (self.bar_length - fill_width)
        
        sys.stdout.write(f'\r[{bar}] {self.frac*100.:.2f}%')
        sys.stdout.flush()

        if frac == 1.:
            print('')


@dataclass
class Library:
    root_dependencies: dict = field(default_factory=dict)
    other_dependencies: dict = field(default_factory=dict)
    missing_files: set = field(default_factory=set)

    def __contains__(self, element):
        in_root = element in self.root_dependencies
        in_other = element in self.other_dependencies
        in_missing = element in self.missing_files

        return in_root or in_other or in_missing
    
    def __or__(self, other):
        if isinstance(other, Library):
            new_root_dependencies = {**self.root_dependencies, **other.root_dependencies}
            new_other_dependencies = {**self.other_dependencies, **other.other_dependencies}
            new_missing_files = self.missing_files | other.missing_files

            return Library(new_root_dependencies, new_other_dependencies, new_missing_files)

        return NotImplemented
    
    def __ior__(self, other):
        if isinstance(other, Library):
            self.root_dependencies = {**self.root_dependencies, **other.root_dependencies}
            self.other_dependencies = {**self.other_dependencies, **other.other_dependencies}
            self.missing_files = self.missing_files | other.missing_files
            
            return self
        
        return NotImplemented
            

@dataclass
class Dependency(Library):
    '''
    Simple class for holding on to the result of the dependency check for each root header file
    '''
    all_good: bool = False
    
    def __bool__(self):
        return self.all_good
    


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

def dependencies_satisfied(base_folder, file_path, existing_library):

    #the system paths where the dependencies are checked against
    search_paths = ['/usr/include', '/usr/local/include', '/usr/lib', '/lib/modules']

    #blank set where new found dependencies are inserted
    new_root_dependencies = {}
    new_other_dependencies = {}
    new_missing_dependencies = set()

    logger.trace(f'Starting dependency check on {file_path}...')

    with open(file_path) as file:
        file_content = file.readlines()
    
    #store all directives
    included_files = []
    
    #parse all the code for #include directives
    for line in file_content:
        #strip leading spaces
        line = line.strip()
        #determine if it's an include directory
        if line.startswith('#include') and ('<' in line or '\"' in line):
            # #include <...> type
            if '<' in line and '>' in line:
                include = line.split('<', 1)[1].split('>', 1)[0].strip()
                included_files.append(include)

            # #include "..." type
            if '"' in line:
                include = line.split('"', 2)[1].strip()
                included_files.append(include)

    logger.trace(f'{len(included_files)} #include directive(s) found in {file_path.name}')

    #for each of these included files, check if they are present in the computer
    for inc_file in included_files:
        
        #skip this iteration if the file is already known
        if inc_file in existing_library:
            logger.trace(f'"{inc_file}" is already known. Check will be skipped.')
            continue

        #first check inside the root include directory
        file_complete_paths = list(base_folder.rglob(inc_file))
        if len(file_complete_paths) > 0:
            #even if there are multiple matches, just use the first one and add it to the set
            path_to_include = str(file_complete_paths[0]).replace(inc_file, '')
            new_root_dependencies[inc_file] = path_to_include

            logger.trace(f'Match for "{inc_file}" found inside the root library at {path_to_include}')

        #if this check fails, search for this file anywhere else
        else:
            logger.trace(f'No match for "{inc_file}" found inside the root library, looking elsewhere...')

            file_complete_paths = []
            for search_path in search_paths:
                file_complete_paths += list(Path(search_path).rglob(inc_file))

            #if this file is found somewhere else, add it to the other set
            if len(file_complete_paths) > 0:
                path_to_include = str(file_complete_paths[0]).replace(inc_file, '')
                new_other_dependencies[inc_file] = path_to_include
                logger.trace(f'Match for "{inc_file}" found in system at {path_to_include}"')
            else:
                logger.trace(f'No match for "{inc_file}" found anywhere.')
                #if all checks fail, all this file must not be included
                new_missing_dependencies.add(inc_file)
                return Dependency(missing_files=new_missing_dependencies, all_good=False)
                
            
    
    #return a Dependency object with all the paths 
    return Dependency(new_root_dependencies, new_other_dependencies, all_good=True)



def write_files(out_file, base_folder, relative_path, library = Library()):
    '''
    Writes all header files present in base_folder, starting from relative_path and in all subdirectories, on a single header file `out_file`
    
    Parameters
    ----------
    out_file: file
        the output file object where all include directives will be written (must be already open)
    base_folder: Path
        the folder in which the output file will be placed
    relative_path: Path
        the starting path relative to the base_folder from which to start the searcy
    library: `Library` object
        contains all the information about what include files are present in each header files and where, if at all,
        they are present in the computer

    Returns
    -------
    updated_library: `Library` object
        same as library input, but updated afer the call

    Other functionality
    -------------------
    updates the global variable `out_lines` to match the number of lines written

    '''
    global out_lines
    
    #exclude this file in case it already exists
    excluded_files = ['AllRoot.h', 'rootsense.h']

    #compute the working folder
    working_folder = base_folder / relative_path

    #gather all subfolders of the working folder
    subfolders = [folder.name for folder in working_folder.iterdir() if folder.is_dir()]
    for subfolder in subfolders:
        #recursively call this function on all subfolders and use their output to update the library
        library |= write_files(out_file, base_folder, relative_path + f'{subfolder}/')
        

    #get all the '*.h' and '*.hh' files in this folder
    header_files_paths = [file for file in working_folder.glob('*') if file.suffix in ['.h', '.hh']]
    header_files_names = [filepath.name for filepath in header_files_paths]
    logger.info(f'Parsing {len(header_files_names)} header file(s) found in {working_folder}...')
    #machinery for printing the progress bar for this folder
    bar = ProgressBar()
    total = len(header_files_names)
    if total != 0:
        bar.update()

    for i, (path, name) in enumerate(zip(header_files_paths, header_files_names)):
        #skip iteration if the file is among the excluded ones
        if name in excluded_files:
            continue
        else:
            #make the dependency check and store it in a Dependency object
            dependency_check = dependencies_satisfied(base_folder, path, library)
            #update library with the Dependency
            library |= dependency_check
            #write this file only if it's viable
            if dependency_check:
                out_file.write(f'#include \"{relative_path + name}\"\n')
                out_lines += 1
                logger.trace(f'All dependency checks complete on {path}')
            else:
                logger.trace(f'Dependency checks failed on {path}: file will not be included.')

        frac = (i+1) / total
        bar.update(frac)

    
    return library
            


def main(args):
    #gather start time
    start_time = time.time()

    logger.info('Gathering root install path...')
    #this generates something like '/home/{user}/root/bin/root'
    root_exec_path_result = bash_command('which root')
    if root_exec_path_result.returncode != 0:
        raise OSError('Root installation not found. Make sure root is installed and set in your PATH variable.')

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
        dependencies_library = write_files(file, root_include_folder, '')
        file.write('\n#endif')

    logger.success(f'{out_lines} lines of directives written in "rootsense.h" in {time.time() - start_time:.1f} seconds.')

    #cast library dicts into sets for printing
    root_dependencies_set = set(dependencies_library.root_dependencies.values())
    other_dependencies_set = set(dependencies_library.other_dependencies.values())

    print('\n~' + 50 * '-' + '~')
    print(f'Make sure the following {len(root_dependencies_set)} root paths are added to your VsCode include paths:')
    for path in root_dependencies_set:
        print(path)

    print('\n~' + 50 * '-' + '~')
    print('Other paths for included files elsewhere. They probably are already taken care of by VsCode, but try to add them if you encounter any problems:')
    for path in other_dependencies_set:
        print(path)
    


if __name__ == '__main__':
    prog_description = 'Generate a header file including all root libraries'
    parser = argparse.ArgumentParser(description=prog_description, formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    parser.add_argument('-d', '--dir', default=None, help='Specify the directory where root is installed')
    args = parser.parse_args()

    main(args)