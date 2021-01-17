import setuptools

setuptools.setup(
    name='sqfl',
    version='0.1',
    description='SQL Filter Language',
    url='https://github.com/siikamiika/sqfl',
    author='siikamiika',
    license='MIT',
    py_modules=['sqfl'],
    packages=setuptools.find_packages(),
    python_requires='>=3.8',
    include_package_data=True,
    zip_safe=False
)
