@echo off
echo Testing Python with different flags...

echo.
echo Test 1: Python with -S (no site packages)
python -S -c "print('Works with -S')"

echo.
echo Test 2: Python with -I (isolated mode) 
python -I -c "print('test')"

echo.
echo Test 3: Python with -E (ignore environment)
python -E -c "print('test')"

echo Done!