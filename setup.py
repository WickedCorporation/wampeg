import setuptools

setuptools.setup(
    name="wampeg",
    version="0.1",
    install_requires=["aiofiles"],
    packages=setuptools.find_packages(),
    python_requires=">=3.6",
)