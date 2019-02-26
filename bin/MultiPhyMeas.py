#!/usr/bin/env python3
"""Calculates conservation score for multiple alignments"""
import PhyMeas
import re, os, sys, getopt, plotly, single_cons_comp, argparse
import plotly.graph_objs as go
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import seaborn as sns
import numpy as np
import pandas as pd
#from labellines import labelLine, labelLines
from operator import itemgetter

def create_and_parse_argument_options(argument_list):
	parser = argparse.ArgumentParser(description='Calculate and visualize conservation between two groups of sequences from multiple alignments.')
	parser.add_argument('alignment_path', help='Path to folder with alignment files.')
	parser.add_argument('output_path', help='Path to image for output.')
	parser.add_argument('-t','--threshold', help='Threshold for number of allowed bad scores when calculating length of positive sections.', type=int, default=1, required=False)
	parser.add_argument('-s','--structure_path', help='Path to folder with structure files; names should match alignment groups within files.')
	output_group = parser.add_mutually_exclusive_group(required=True)
	output_group.add_argument('-ps', '--scatter_plot', help='Plots a scatter of the length for positive stretches and their total score.', action="store_true")
	output_group.add_argument('-pr', '--ribbon_plot', help='Plots a 3D ribbon of the length for positive stretches and their total score.', action="store_true")
	output_group.add_argument('-pm', '--multi_plot', help='Plots a scatter of the representation for each alignment. For many (>20) alignments.', action="store_true")
	commandline_args = parser.parse_args(argument_list)
	return commandline_args

def lookahead(iterable):
	"""Pass through all values from the given iterable, augmented by the
	information if there are more values to come after the current one
	(True), or if it is the last value (False).
	"""
	# Get an iterator and pull the first value.
	it = iter(iterable)
	last = next(it)
	# Run the iterator to exhaustion (starting from the second value).
	for val in it:
		# Report the *previous* value (more to come).
		yield last, True
		last = val
	# Report the last value.
	yield last, False

def make_length_distr(df,comm_args,group_dict):
	'''
	Takes in dataframe with values per file and returns
	a length distribution dictionary with keys files and
	values lengths of uninterrupted positive scoring positions.
	(Can be interupted by 1 low scoring position (or more set with -t)
	This means that a sequence of ++-+-+-+-- will have a length of 5)
	'''
	length_distr={}
	weight_distr={}
	thr_distr = comm_args.threshold
	for file in df:
		i=0
		k=0
		w=0
		alignment_length = len(group_dict[file])
		for pos,has_more in lookahead(df[file]):
			if pos is None:
				pass
			else:
				if pos > 0.5:
					#print(i, 'greater')
					k=0
					i+=1
					w+=pos
				elif pos <= 0.5:
					if k == thr_distr:
						#print(i, 'smaller k is threshold')
						if file in length_distr.keys():
							length_distr[file].append(i)
							if i > 0:
								weight_distr[file].append((i,w/i))
							else:
								weight_distr[file].append((i,0))
							w=0
							i=0
							k=0
						else:
							length_distr[file]=[]
							weight_distr[file]=[]
							length_distr[file].append(i)
							if i > 0:
								weight_distr[file].append((i,w/i))
							else:
								weight_distr[file].append((i,0))
							w=0
							i=0
							k=0
					elif k < thr_distr:
						#print(i, 'smaller k is not threshold')
						#w+=pos #Think about this one
						#i+=1	#Think about that one
						k+=1
			if has_more is False:
				#print(i, 'last')
				if file in length_distr.keys():
					length_distr[file].append(i)
					if i > 0:
						weight_distr[file].append((i,w/i))
					else:
						weight_distr[file].append((i,0))
					w=0
					i=0
				else:
					length_distr[file]=[]
					weight_distr[file]=[]
					length_distr[file].append(i)
					if i > 0:
						weight_distr[file].append((i,w/i))
					else:
						weight_distr[file].append((i,0))
					w=0
					i=0
	return length_distr, weight_distr

def slope(point1, point2):
	if point2[0]-point1[0] != 0:
		return np.arctan2(point2[1]-point1[1],point2[0]-point1[0])
	else:
		return np.arctan2(point2[1]-point1[1],point2[0]-point1[0])

def ribbon_plot(newdict, bin_edges,output_path):
	traces = []
	xtickvals = []
	y_raw = bin_edges
	samples = sorted(list(newdict.keys()))
	sample_labels = [re.compile(r"\..*").sub("", m) for m in samples]
	for i in range(0, len(samples)):
		xtickvals.append((i+1)*2+0.5)
		z_raw = newdict[samples[i]]
		#print(samples[i],z_raw)
		#print(samples[i],sum(z_raw*range(len(z_raw)))/sum(z_raw))
		x = []
		y = []
		z = []
		for j in range(1, len(z_raw)):
			z.append([z_raw[j], z_raw[j]])
			y.append([y_raw[j], y_raw[j]])
			x.append([(i+1)*2, (i+1)*2+1])
		traces.append(dict(z=z, x=x, y=y, showscale=False, type='surface'))
	layout = go.Layout(
						title='Segment length distributions',
						scene = dict(
						xaxis=dict(
							tickmode="array", ticktext=sample_labels, tickvals=xtickvals),
						yaxis=dict(
							title="Length of uninterrupted positive scores"),
						zaxis=dict(
							title="Number of segments"))
						)
	fig = go.Figure(data=traces, layout=layout)
	plotly.offline.plot(fig, filename=output_path)

def scatter_plot(comm_args,weight_distr):
	ax = plt.subplot()
	if len(weight_distr) == 10:
		colors = matplotlib.cm.seismic(np.linspace(0, 1, len(weight_distr)))
	else:
		colors = matplotlib.cm.tab20(np.linspace(0, 1, len(weight_distr)))
	sorted_names = sorted(weight_distr.keys())
	for file, color in zip(sorted_names,colors):
		degree_label = 180-round(np.rad2deg(slope(weight_distr[file][0],weight_distr[file][1])),2)
		plt.scatter(*zip(*weight_distr[file]), label=str(degree_label)+' '+re.sub(r'\.fas.*','',file), marker='.',color=color)
		plt.plot(*zip(*weight_distr[file]),color=color)

	#labelLines(plt.gca().get_lines(),align=False)
	plt.legend(bbox_to_anchor=(1.04,1), borderaxespad=0)
	plt.savefig(comm_args.output_path, dpi=600, bbox_inches='tight')
	return True

def make_hist(input_dict):
	maxlength=0
	for file in input_dict:
		if maxlength < max(input_dict[file]):
			maxlength = max(input_dict[file])
	bins = list(range(0,int(maxlength)+1))
	newdict={}
	for file in input_dict:
		hist, bin_edges = np.histogram(input_dict[file], bins=bins)
		newdict[file]=hist
	return newdict, bin_edges

def main(commandline_args):

	comm_args = create_and_parse_argument_options(commandline_args)
	group_dict={}
	aln_length={}
	for file in os.listdir(comm_args.alignment_path):
		if re.findall(r'(.*\/)(.*)(\.fasta|\.fas)',comm_args.alignment_path+file):
			# print(file)
			out_dict={}
			alnindex_score,sliced_alns=PhyMeas.main([comm_args.alignment_path+file, '-r', '-bl'])
			for x in sliced_alns:
				aln_length[file]=sliced_alns[x].get_alignment_length()
				break
			for x in alnindex_score.keys():
				out_dict[x] = alnindex_score[x][0]
			group_dict[file] = out_dict
		else:
			raise ValueError("Directory must have only .fas or .fasta alignment files!")
	df = pd.DataFrame.from_dict(group_dict)
	length_distr, weight_distr = make_length_distr(df,comm_args,group_dict)
	
	if comm_args.ribbon_plot:
		lendict, len_bin_edges = make_hist (length_distr)
		ribbon_plot(lendict, len_bin_edges,comm_args.output_path)
		#weidict, wei_bin_edges = make_hist (weight_distr)
		#ribbon_plot(weidict, wei_bin_edges,comm_args.output_path)
	elif comm_args.scatter_plot:
		scatter_plot(comm_args,weight_distr)
	elif comm_args.multi_plot:
		maxweight={}
		for file in weight_distr.keys():
			maxweight[file]=[max(weight_distr[file],key=itemgetter(0)),max(weight_distr[file],key=itemgetter(1))]
			#print(file, slope(maxweight[file][0],maxweight[file][1]))
		scatter_plot(comm_args,maxweight)


if __name__ == "__main__":
	main(sys.argv[1:])