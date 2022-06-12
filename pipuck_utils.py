#!/usr/bin/env python3

import argparse
import subprocess
import robots


def run_command(command, hide_output):
		if hide_output:
			process = subprocess.Popen(command, shell=True, stdout=subprocess.PIPE)
		else:
			process = subprocess.Popen(command, shell=True)
		process.wait()
		code = process.returncode
		if code == 0:
			return 'OK'
		else:
			return 'ERROR'


if __name__ == '__main__':
	parser = argparse.ArgumentParser(description='Pi-puck management utilities.')
	parser.add_argument('utility', choices=['ping', 'ssh-copy-id', 'copy-server', 'shutdown', 'reboot', 'battery'])

	args = parser.parse_args()
	if args.utility == 'ping':
		for (robot_id, ip) in robots.pipucks.items():
			if ip != '':
				result = run_command(f'ping -c2 -t3 {ip}', True)
				print(f'{robot_id}: {result}')
	elif args.utility == 'ssh-copy-id':
		for (robot_id, ip) in robots.pipucks.items():
			if ip != '':
				result = run_command(f'ssh-copy-id -o StrictHostKeyChecking=no pi@{ip}', False)
				print(f'{robot_id}: {result}')
	elif args.utility == 'copy-server':
		for (robot_id, ip) in robots.pipucks.items():
			if ip != '':
				result = run_command(f'scp pipuck_server.py pi@{ip}:', False)
				print(f'{robot_id}: {result}')
	elif args.utility == 'shutdown':
		for (robot_id, ip) in robots.pipucks.items():
			if ip != '':
				result = run_command(f'ssh pi@{ip} sudo poweroff', False)
				print(f'{robot_id}: {result}')
	elif args.utility == 'reboot':
		for (robot_id, ip) in robots.pipucks.items():
			if ip != '':
				result = run_command(f'ssh pi@{ip} sudo reboot', False)
				print(f'{robot_id}: {result}')
	elif args.utility == 'battery':
		for (robot_id, ip) in robots.pipucks.items():
			if ip != '':
				print(f'Checking battery on robot {robot_id}...')
				result = run_command(f'ssh pi@{ip} pi-puck-battery', False)
				print(f'{robot_id}: {result}')
				print()
