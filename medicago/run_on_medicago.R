#!/usr/bin/Rscript --vanilla
library(optparse)

invocation <- commandArgs()

usage <- "\
Does a local PCA analysis on the Medicago truncatula hapmap data (see medicago_data_setup.html for details).
"

option_list <- list(
    # input/output
        make_option( c("-t","--type"),   type="character",             help="Window by SNP or by bp?"),
        make_option( c("-s","--size"),   type="integer",               help="Size of the window, in units of type."),
        make_option( c("-k","--npca"),   type="integer",   default=2L, help="Number of principal components to compute for each window. [default: %default]"),
        make_option( c("-m","--nmds"),   type="integer",   default=2L, help="Number of principal coordinates (MDS variables) to compute. [default: %default]"),
        make_option( c("-o","--outdir"), type="character",             help="Directory to save results to.  [default: lostruct/results_%type_%size_%jobid/]"),
        make_option( c("-j","--jobid"),  type="character", default=formatC(1e6*runif(1),width=6,format="d",flag="0"),   help="Unique job id. [default random]")
    )
opt <- parse_args(OptionParser(option_list=option_list,description=usage))
if (is.null(opt$outdir)) { opt$outdir <- file.path("lostruct", sprintf( "results_%s_%d_%s", opt$type, opt$size, opt$jobid ) ) }
print(opt) # this will go in the logfile
Sys.time()

dir.create( opt$outdir, showWarnings=FALSE, recursive=TRUE )

# setup
devtools::load_all("../package")

# VCF files
chroms <- paste0("chr",1:8)
bcf.files <- file.path( "data", paste0(chroms,"-filtered-set-2014Apr15.bcf") )
names(bcf.files) <- chroms

all.pcas <- numeric(0)

# local PCA, by chromosome
for (bcf.file in bcf.files) {
    pca.file <- file.path( opt$outdir, sprintf(gsub(".bcf",".pca.csv",bcf.file)) )
    if (file.exists(pca.file)) { stop(paste("File",pca.file,"already exists! Not overwriting.")) }
    cat("Finding PCs for", bcf.file, "and writing out to", pca.file, "\n")
    win.fn <- vcf_windower(bcf.file, size=opt$size, type=tolower(opt$type) )
    system.time( pca.stuff <- eigen_windows( win.fn, k=opt$npca, return.mat=TRUE ) )
    write.csv( t(pca.stuff), file=pca.file )
    all.pcas <- rbind( all.pcas, t(pca.stuff) )
}
rm(pca.stuff)

# distance matrix
cat("Done finding PCs, computing distances.\n")
system.time( pc.distmat <- pc_dist( all.pcas ) )

# MDS on the resulting distance matrix
mds.file <- file.path( opt$outdir, "mds_coords.csv" )
cat("Done computing distances, running MDS and writing results to", mds.file, "\n")
na.inds <- is.na( all.pcs[,1] ) # there may be windows with missing data
mds.coords <- cmdscale( pc.distmat[!na.inds,!na.inds], k=opt$nmds )[ ifelse( na.inds, NA, cumsum(!na.inds) ), ]
colnames(mds.coords) <- paste("MDS coordinate", 1:ncol(mds.coords))
write.csv( mds.coords, mds.file, header=TRUE )

cat("All done!")
Sys.time()