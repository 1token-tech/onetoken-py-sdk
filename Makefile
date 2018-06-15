default:
	make clean
	python3 setup.py sdist bdist_wheel && cd dist && pip3 install onetoken*whl --upgrade

clean:
	rm dist build onetoken.egg-info -rf
