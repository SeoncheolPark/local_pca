#!/usr/bin/env python
description = '''
Convert simulations to msprime and VCF.
'''

import gzip
import sys
from optparse import OptionParser
import math
import time
import random
import msprime
import ftprime

def fileopt(fname,opts):
    '''Return the file referred to by fname, open with options opts;
    if fname is "-" return stdin/stdout; if fname ends with .gz run it through gzip.
    '''
    if fname == "-":
        if opts == "r":
            fobj = sys.stdin
        elif opts == "w":
            fobj = sys.stdout
        else:
            print("Something not right here.")
    elif fname[len(fname)-3:len(fname)]==".gz":
        fobj = gzip.open(fname,opts)
    else:
        fobj = open(fname,opts)
    return fobj

parser = OptionParser(description=description)
parser.add_option("-i","--infile",dest="infile",help="input file (output by background-sim.py)")
parser.add_option("-k","--nsamples",dest="nsamples",help="number of *diploid* samples, total")
parser.add_option("-A","--ancestor_age",dest="ancestor_age",help="time to ancestor above beginning of sim")
parser.add_option("-u","--mut_rate",dest="mut_rate",help="mutation rate",default=1e-7)
parser.add_option("-o","--outfile",dest="outfile",help="name of output file (or '-' for stdout)",default="-")
parser.add_option("-t","--treefile",dest="treefile",help="name of output file for trees (or '-' for stdout)")
parser.add_option("-g","--logfile",dest="logfile",help="name of log file (or '-' for stdout)",default="-")
(options,args) =  parser.parse_args()

infile = fileopt(options.infile, "r")
outfile = fileopt(options.outfile, "w")
logfile = fileopt(options.logfile, "w")

logfile.write("Options:\n")
logfile.write(str(options)+"\n")

nsamples=int(options.nsamples)
mut_rate=float(options.mut_rate)
ancestor_age=float(options.ancestor_age)

# Read in from the file::
#   generations
#   length
#   N

name,val = infile.readline().split(":")
if name != "# generations":
    raise ValueError("Bad file format.")
else:
    generations = int(val.strip())
print("generations: ",generations)

name,val = infile.readline().split(":")
if name != "# length":
    raise ValueError("Bad file format.")
else:
    length = float(val.strip())
print("length: ",length)

# total number of individuals; needed for translating indiv id to time
name,val = infile.readline().split(":")
if name != "# N":
    raise ValueError("Bad file format.")
else:
    N = int(val.strip())
print("N: ",N)

# locus positions
name,val = infile.readline().split(":")
if name != "# loci":
    raise ValueError("Bad file format.")
else:
    locus_position = [0.0] + [float(x) for x in val.split()] + [length]
# print("locus_position: ",locus_position)


def ind_to_time(k):
    return 1+generations-math.floor((k-1)/N)

def i2c(k,p):
    # individual ID to chromsome
    # "1+" is for the universal common ancestor added below
    out=1+2*nsamples+ftprime.ind_to_chrom(k,ftprime.mapa_labels[p])
    return out

# Input is of this form:
# offspringID parentID startingPloidy rec1 rec2 ....
# ... coming in *pairs*

args=ftprime.ARGrecorder()
# Add the ancestor of everyone, labeled nsamples
universal_ancestor=2*nsamples
args.add_individual(name=universal_ancestor,time=float(1+generations+ancestor_age))
# add initial generation
first_gen = [i2c(k,p) for k in range(1,N+1) for p in [0,1]]
first_gen.sort()
args.add_record(0.0,length,universal_ancestor,tuple(first_gen))
for k in range(1,N+1): 
    for p in [0,1]:
        args.add_individual(i2c(k,p),ind_to_time(k))


nlines=0
log_lines=10000

while True:
    line=infile.readline()
    if not line:
        break
    if (nlines%log_lines==0):
        logfile.write("Reading line "+str(nlines)+"\n")
        logfile.flush()
    nlines+=1
    # print("A: "+line)
    # child,parent,ploid,*rec = [int(x) for x in line.split()]
    linex = [int(x) for x in line.split()]
    child=linex[0]
    parent=linex[1]
    ploid=linex[2]
    rec=linex[3:]
    for child_p in [0,1]:
        if child_p==1:
            line=infile.readline()
            # print(" : "+line)
            prev_child=child
            # child,parent,ploid,*rec = [int(x) for x in line.split()]
            linex = [int(x) for x in line.split()]
            child=linex[0]
            parent=linex[1]
            ploid=linex[2]
            rec=linex[3:]
            if child != prev_child:
                raise ValueError("Recombs not in pairs:"+str(child)+"=="+str(prev_child))
        # print(child,child_p,parent,ploid)
        if ind_to_time(child)>ind_to_time(parent):
            raise ValueError(str(child)+" at "+str(ind_to_time(child))+" does not come after " + str(parent)+" at "+str(ind_to_time(parent)))
        start=0.0
        child_chrom=i2c(child,child_p)
        # print(".. Adding",child_chrom)
        args.add_individual(child_chrom,ind_to_time(child))
        for r in rec:
            breakpoint=random.uniform(locus_position[r],locus_position[r+1])
            # print("--- ",start,breakpoint)
            args.add_record(
                    left=start,
                    right=breakpoint,
                    parent=i2c(parent,ploid),
                    children=(child_chrom,))
            start=breakpoint
            ploid=((ploid+1)%2)
        # print("--- ",start,length," |")
        args.add_record(
                left=start,
                right=length,
                parent=i2c(parent,ploid),
                children=(child_chrom,))


#######

# final pop IDs
pop_ids = range(1+generations*N,1+(1+generations)*N)

# some messing around to fill up the required samples
diploid_samples=random.sample(pop_ids,nsamples)
logfile.write("Samples ("+str(nsamples)+" of them): "+str(diploid_samples)+"\n")
logfile.flush()
# need chromosome ids
chrom_samples = [ ftprime.ind_to_chrom(x,a) for x in diploid_samples for a in ftprime.mapa_labels ]
args.add_samples(samples=chrom_samples,length=length)

# not really the sample locs, but we don't care about that
sample_locs = [ (0,0) for _ in chrom_samples ]

# for x in args.dump_records():
#     print(x)

logfile.write("Constructing tree sequence.\n")
logfile.flush()

ts=args.tree_sequence(samples=sample_locs)

# print("msprime trees:")
# for x in ts.records():
#     print(x)

logfile.write("Simplifying tree sequence.\n")
logfile.flush()

ts.simplify(samples=list(range(nsamples)))

if options.treefile is not None:
    logfile.write("Dumping trees to"+options.treefile+"\n")
    logfile.flush()
    ts.dump(options.treefile)

mut_seed=random.randrange(1,1000)
logfile.write("Generating mutations with seed "+str(mut_seed)+"\n")
logfile.flush()
rng = msprime.RandomGenerator(mut_seed)
ts.generate_mutations(mut_rate,rng)

logfile.write("Done!\n")
logfile.write(time.strftime('%X %x %Z')+"\n")
logfile.write("Mean pairwise diversity: {}\n".format(ts.get_pairwise_diversity()/ts.get_sequence_length()))
logfile.write("Sequence length: {}\n".format(ts.get_sequence_length()))
logfile.write("Number of trees: {}\n".format(ts.get_num_trees()))
logfile.write("Number of mutations: {}\n".format(ts.get_num_mutations()))

print("Writing out vcf to",outfile)
ts.write_vcf(outfile,ploidy=1)



