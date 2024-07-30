from cx_Freeze import setup, Executable

# Dependencies are automatically detected, but it might need
# fine tuning.
build_options = {'packages': [], 'excludes': [], 'include_files': [('config.ini', 'config.ini')]}

base = 'console'

executables = [
    Executable('seekers.py', base=base, target_name = 'run_seekers'),
    Executable('client.py', base=base, target_name = 'run_client')
]

setup(name='compile_test',
      version = '1.0',
      description = 'bla',
      options = {'build_exe': build_options},
      executables = executables)