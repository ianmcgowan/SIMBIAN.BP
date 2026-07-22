#!/usr/bin/env perl
use strict;
use warnings;
use Getopt::Long qw(GetOptions);
use File::Basename qw(fileparse);
use Excel::Writer::XLSX;

sub print_usage {
    print <<"USAGE";
Usage:
  $0 [options] <output.xlsx> <input_file1> [input_file2 ...]

Options:
  -d, --delimiter <delim>   Specify field delimiter.
                             Supported options: tab (default), pipe, comma, semicolon (or semi-colon).
                             Literal characters are also accepted (e.g. -d "|", -d "\\t", -d ",").
  -h, --help                Display this help message.

Examples:
  $0 output.xlsx data1.txt data2.txt
  $0 -d pipe output.xlsx data1.psv data2.psv
  $0 -d comma output.xlsx export1.csv export2.csv
USAGE
    exit 1;
}

my $delim_arg = 'tab';
my $help      = 0;

GetOptions(
    'delimiter|d=s' => \$delim_arg,
    'help|h'        => \$help,
) or print_usage();

print_usage() if $help || @ARGV < 2;

my $output_excel = shift @ARGV;
my @input_files  = @ARGV;

# Map delimiter argument to separator character
my $sep_char;
my $lc_delim = lc($delim_arg);

if ($lc_delim eq 'tab' || $delim_arg eq "\t" || $delim_arg eq '\t') {
    $sep_char = "\t";
} elsif ($lc_delim eq 'pipe' || $delim_arg eq '|') {
    $sep_char = "|";
} elsif ($lc_delim eq 'comma' || $delim_arg eq ',') {
    $sep_char = ",";
} elsif ($lc_delim eq 'semicolon' || $lc_delim eq 'semi-colon' || $delim_arg eq ';') {
    $sep_char = ";";
} else {
    if (length($delim_arg) == 1) {
        $sep_char = $delim_arg;
    } else {
        die "Error: Unknown delimiter '$delim_arg'. Supported: tab, pipe, comma, semicolon.\n";
    }
}

# Create Excel Workbook
my $workbook = Excel::Writer::XLSX->new($output_excel);
die "Error: Could not create Excel workbook '$output_excel': $!\n" unless $workbook;

my %seen_sheets;

for my $file (@input_files) {
    unless (-e $file) {
        warn "Warning: File '$file' does not exist. Skipping.\n";
        next;
    }

    open my $fh, '<', $file or do {
        warn "Warning: Could not open file '$file': $!. Skipping.\n";
        next;
    };

    # Derive sheet name from file basename (without file extension)
    my ($base_name) = fileparse($file, qr/\.[^.]*/);

    # Remove forbidden Excel sheet name characters: \ / ? * [ ] :
    $base_name =~ s/[\\\/?\*\[\]:]//g;
    $base_name = 'Sheet' if $base_name eq '';

    # Truncate to maximum 31 characters allowed by Excel
    $base_name = substr($base_name, 0, 31);

    # Ensure sheet name uniqueness
    my $sheet_name = $base_name;
    my $counter    = 1;
    while ($seen_sheets{lc($sheet_name)}) {
        my $suffix       = "_$counter";
        my $max_base_len = 31 - length($suffix);
        $sheet_name      = substr($base_name, 0, $max_base_len) . $suffix;
        $counter++;
    }
    $seen_sheets{lc($sheet_name)} = 1;

    my $worksheet = $workbook->add_worksheet($sheet_name);

    my $row = 0;
    while (my $line = <$fh>) {
        $line =~ s/\r?\n$//;
        my @row_data = split(/\Q$sep_char\E/, $line, -1);
        my $col = 0;
        for my $cell (@row_data) {
            # Force all fields to be written strictly as text
            $worksheet->write_string($row, $col, defined $cell ? $cell : '');
            $col++;
        }
        $row++;
    }

    close $fh;
}

$workbook->close();
print "Successfully created '$output_excel'.\n";
