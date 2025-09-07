#!/usr/bin/env python3

import json, sys, os, re
import urllib.parse

import subprocess

import argparse

from collections import namedtuple

parser = argparse.ArgumentParser()
parser.add_argument('--convert_photo_script', action='store_true')
parser.add_argument('--local_paths', action='store_true')
args = parser.parse_args()

# This is like `ls blah/* blah1/* > list-of-all-photo.txt`
image_paths = list(line.strip() for line in open('list-of-all-photo.txt'))
basename2path = { os.path.basename(path): path for path in image_paths }
assert len(basename2path) == len(image_paths), 'Unique basenames pleaes'

def pandoc_htmlfile2json(path):
	process = subprocess.Popen(
		['pandoc', '--from', 'markdown+lists_without_preceding_blankline', '--to', 'json', path],
		# stdin=subprocess.PIPE,
		stdout=subprocess.PIPE,
		stderr=subprocess.PIPE,
		text=True          # This allows us to handle strings instead of bytes
	)

	# Send the text to stdin and capture stdout
	stdout, stderr = process.communicate()

	# Raise an error if the command failed
	if process.returncode != 0:
		raise RuntimeError(f"Command failed with error: {stderr}")

	return json.loads(stdout)

def pandocjson2html(j):
	process = subprocess.Popen(
		['pandoc', '--from', 'json', '--to', 'html'],            # Command as a list
		stdin=subprocess.PIPE,
		stdout=subprocess.PIPE,
		stderr=subprocess.PIPE,
		text=True          # This allows us to handle strings instead of bytes
	)

	# Send the text to stdin and capture stdout
	stdout, stderr = process.communicate(input=json.dumps(j))

	# Raise an error if the command failed
	if process.returncode != 0:
		raise RuntimeError(f"Command failed with error: {stderr}")

	return stdout

def flat(xss):
	return (x for xs in xss for x in xs)

# traverse pandoc ast
def postmap_pandoc(f):
	def help(j):
		c = j.get('c', None)
		match j['t']:
			case 'Table':
				pass # TODO: a
			case 'Header':
				c[2] = list(flat(map(help, c[2])))
			case 'Para' | 'Emph' | 'BlockQuote' | 'Plain':
				j['c'] = list(flat(map(help, j['c'])))
			case 'Image' | 'Quoted' | 'Div' | 'Link':
				c[1] = list(flat(map(help, c[1])))
			case 'OrderedList': # OrderedList ListAttributes [[Block]]
				c[1] = [list(flat(map(help, lst))) for lst in c[1]]
			case 'BulletList': # BulletList [[Block]]
				j['c'] = [list(flat(map(help, lst))) for lst in j['c']]
			# case ''
			case 'Str' | 'Space' | 'SoftBreak' | 'RawInline' | 'RawBlock' | 'CodeBlock' | 'Code': pass
			case _: assert False, f"Do not know how to process pandoc element: {j}"
		return f(j)
	return help

# find any that meet it
def find(pred):
	def help(target):
		result = []
		def f(j):
			# nonlocal result
			if pred(j):
				result.append(j)
			return [j]
		postmap_pandoc(f)(target)
		return result
	return help

def ri(html):
	return { 't': 'RawInline', 'c': ['html', html] }
def mkstr(s):
	return { 't': 'Str', 'c': s }

def is_h1(j):
	return j['t'] == 'Header' and j['c'][0] == 1


pages = \
	[ *[f"{i+1}.md" for i in range(17)]
	]
pages = [f"markdown/{path}" for path in pages]

def basebasename(path):
	return re.sub(r'\.\w+$', '', os.path.basename(path))

def convert_media_logic(path): # -> (new path, convert command)
	basename = os.path.basename(path)
	if path.lower().endswith('.jpg'):
		newpath = f"media/{basebasename(basename)}.webp"
		return newpath, f'convert -verbose -auto-orient "{path}" "docs/{newpath}"'
	else:
		assert False, f"idk how to handle this basename: {basename}"

Page = namedtuple('Page', ['title', 'asides', 'images', 'html'])

def medianame2mediapath(name): # name is what i typed in the link
	realpath = basename2path[name]
	if args.local_paths:
		return re.sub(r'^/mnt/c', 'file://C:', realpath) # set href
	else:
		newpath, _ = convert_media_logic(realpath)
		return newpath

ORIGINAL_IMAGE_BASENAMES = []

def process_page(filename): # -> html content
	global ORIGINAL_IMAGE_BASENAMES
	asides = [] # (id, header text)
	images = [] # (id, image url)

	def mypostmap(j):
		match j['t']:
			case 'Image':
				target = j['c'][2]

				ORIGINAL_IMAGE_BASENAMES.append(target[0])
				target[0] = medianame2mediapath(target[0])

				j['c'][2] = target
				j['c'][0][0] = basebasename(target[0]) # set id

				images.append((j['c'][0][0], target[0]))

				return [j]
			case 'Link':
				_, orig, [url, title] = j['c']
				# const [_, [...basething], [explain]] = c
				return [ ri('<ruby>'), *orig, ri('<rt>'), mkstr(urllib.parse.unquote(url)), ri('</rt>'), ri('</ruby>') ]
			case 'Div':
				id, classes, kv_pairs = j['c'][0]
				blocks = j['c'][1]

				if 'aside' in classes:
					h1s = list(flat(find(is_h1)(blk) for blk in blocks))
					assert len(h1s) == 1, f"Expected 1 h1 in the aside but got {len(h1s)}: {j}"
					for h1 in h1s:
						h1['c'][0] = 2
						asides.append((h1['c'][1][0], h1['c'][2]))
				return [j]
			case _: return [j]

	j = pandoc_htmlfile2json(filename)

	j['blocks'] = list(flat(postmap_pandoc(mypostmap)(blk) for blk in j['blocks']))

	# separate from first call because i transformed aside h1 into h2
	h1s = list(flat(find(is_h1)(blk) for blk in j['blocks']))
	assert len(h1s) == 1, f"Expected that there will be 1 h1 but i found {len(h1s)}: {filename}"

	title = h1s[0]['c'][2] # [Inline]

	html = '<!DOCTYPE html><link rel=stylesheet href=style.css /><meta name="viewport" content="width=device-width, initial-scale=1.0, user-scalable=yes" />' + pandocjson2html(j)

	return Page(title, asides, images, html)

def justC(t):
	def f(c):
		return {"t": t, "c": c}
	return f

def noC(t):
	return {"t": t}

def mklink(inlines, url):
	return justC('Link')([['', [], []], inlines, [url, '']])

plain = justC("Plain") # c is [Inline]
bullet_list = justC("BulletList") # c is [[Block]]

listblks = []
photo_list = [] # [id, image url]

for path in pages:
	title, asides, images, html = process_page(path)

	url = f'{basebasename(path)}.html'

	for id, pic_url in images:
		photo_list.append([f"{url}#{id}", pic_url])

	open(f"docs/{url}", 'w').write(html)

	asides_list = bullet_list([[plain([mklink(inlines, f"{url}#{id}")])] for id, inlines in asides])

	# print(asides_list)

	listblks.append([plain([mklink(title, url), noC('Space'), justC("Str")(f"({len(images)} pictures)")]), asides_list])

def map_index(j):
	match j['t']:
		case 'CodeBlock':
			if j['c'][1] == 'table of contents':
				return [bullet_list(listblks)]
			if j['c'][1] == 'inject photo list':
				return [justC('RawBlock')(['html', f"<script>const photo_list = {json.dumps(photo_list)}</script>"])]
			return [j]
		case _: return [j]

if args.convert_photo_script:
	for basename in ORIGINAL_IMAGE_BASENAMES:
		_, convert_script = convert_media_logic(basename2path[basename])
		print(convert_script)
		print()
	# exit()

index_j = pandoc_htmlfile2json('markdown/index.md')
index_j['blocks'] = list(flat(postmap_pandoc(map_index)(blk) for blk in index_j['blocks']))
index_html = '<!DOCTYPE html><link rel=stylesheet href=style.css /><meta name="viewport" content="width=device-width, initial-scale=1.0, user-scalable=yes" />' + pandocjson2html(index_j)

open("docs/index.html", 'w').write(index_html)
