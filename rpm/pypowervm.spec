# Spec file for pypowervm package
Summary: Python API wrapper for PowerVM
Name: pypowervm
BuildArch: noarch
Version: %{_pvm_version}
Release: %{_pvm_release}
Group: Applications/System
License: IBM Corp.
Packager: IBM
URL: http://github.com/powervm/pypowervm
Vendor: IBM Corp.
Requires: python3.6
Requires: python3-pip
Requires: python3-lxml
Requires: python3-six >= 1.7.0

%install 
python3 -m pip install taskflow

%description
Python API wrapper for PowerVM


%build
# Build logic taken from debian/rules file. site-packages directory is used for RHEL
PYVERSION=python$(python -c 'import sys; print("%s.%s" % (sys.version_info[0], sys.version_info[1]))')
python setup.py clean -a
mkdir -p $RPM_BUILD_ROOT/usr/lib/$PYVERSION/site-packages/
python setup.py install --no-compile --root=$RPM_BUILD_ROOT --install-lib=/usr/lib/$PYVERSION/site-packages/ --install-scripts=/usr/lib/$PYVERSION/site-packages/
find $RPM_BUILD_ROOT/usr/lib/$PYVERSION/site-packages -type f -name "*.pyc" -delete
for lc in $(ls -d pypowervm/locale/*/ | cut -f3 -d'/'); do
    mkdir -p $RPM_BUILD_ROOT/usr/share/locale/$lc/LC_MESSAGES
    python setup.py compile_catalog -f --input-file $RPM_SOURCE_DIR/pypowervm/locale/$lc/pypowervm.po --output-file $RPM_BUILD_ROOT/usr/share/locale/$lc/LC_MESSAGES/pypowervm.mo
done


%files

%attr (755, root, root) /usr/lib/python*/site-packages/*
%attr (744, root, root) /usr/share/locale/*/LC_MESSAGES/*

%clean
echo "Do NOT clean the buildroot directory"
