# --------------------------------------------------------
# Dense-Captioning Events in Videos Eval
# Copyright (c) 2017 Ranjay Krishna
# Licensed under The MIT License [see LICENSE for details]
# Written by Ranjay Krishna
# --------------------------------------------------------

import argparse
import json
import sys
sys.path.insert(0, './coco-caption') # Hack to allow the import of pycocoeval

from pycocoevalcap.tokenizer.ptbtokenizer import PTBTokenizer
from pycocoevalcap.bleu.bleu import Bleu
from pycocoevalcap.meteor.meteor import Meteor
from pycocoevalcap.rouge.rouge import Rouge
from pycocoevalcap.cider.cider import Cider
from sets import Set

class ANETcaptions(object):
    PREDICTION_FIELDS = ['results', 'version', 'external_data']

    def __init__(self, ground_truth_filenames=None, prediction_filename=None,
                 tious=None, prediction_fields=PREDICTION_FIELDS,
                 verbose=False):
        # Check that the gt and submission files exist and load them
        if len(tious) == 0:
            raise IOError('Please input a valid tIoU.')
        if not ground_truth_filenames:
            raise IOError('Please input a valid ground truth file.')
        if not prediction_filename:
            raise IOError('Please input a valid prediction file.')

        self.verbose = verbose
        self.tious = tious
        self.pred_fields = prediction_fields
        self.ground_truths = self.import_ground_truths(ground_truth_filenames)
        self.prediction = self.import_prediction(prediction_filename)

    def import_prediction(self, prediction_filename):
        if self.verbose:
            print "| Loading submission..."
        submission = json.load(open(prediction_filename))
        if not all([field in submission.keys() for field in self.pred_fields]):
            raise IOError('Please input a valid ground truth file.')
        return submission['results']

    def import_ground_truths(self, ground_truth_filenames):
        gts = []
        filenames = ground_truth_filenames.split(',')
        self.n_ref_vids = Set()
        for filename in filenames:
            gt = json.load(open(filename))
            self.n_ref_vids.update(gt.keys())
            gts.append(gt)
        if self.verbose:
            print "| Loading GT. #files: %d, #videos: %d" % (len(filenames), len(self.n_ref_vids))
        return gts

    def iou(self, interval_1, interval_2):
        start_i, end_i = interval_1[0], interval_1[1]
        start, end = interval_2[0], interval_2[1]
        intersection = max(0, min(end, end_i) - max(start, start_i))
        union = min(max(end, end_i) - min(start, start_i), end-start + end_i-start_i)
        iou = float(intersection) / (union + 1e-8)
        return iou

    def evaluate(self):
        aggregator = {}
        for tiou in self.tious:
            scores = self.evaluate_tiou(tiou)
            for metric, score in scores.items():
                if metric not in aggregator:
                    aggregator[metric] = []
                aggregator[metric].append(score)
        self.scores = {}
        for metric in aggregator:
            scores = aggregator[metric]
            self.scores[metric] = sum(scores)/len(scores)

    def evaluate_tiou(self, tiou):
        # For every prediction, find it's respective references with tIoU > the passed in argument.
        res = {}
        gts = {}
        unique_index = 0
        for vid_id in self.prediction:
            for pred in self.prediction[vid_id]:
                res[unique_index] = [{'caption': pred['sentence']}]
                matches = []
                for gt in self.ground_truths:
                    refs = gt[vid_id]
                    for ref_i, ref_timestamp in enumerate(refs['timestamps']):
                        if self.iou(pred['timestamp'], ref_timestamp) > tiou:
                            matches.append(refs['sentences'][ref_i])
                gts[unique_index] = [{'caption': v} for v in matches]
                unique_index += 1

        # Set up scorers
        if self.verbose:
            print '| Tokenizing ...'
        # Suppressing tokenizer output
        tokenizer = PTBTokenizer()
        gts  = tokenizer.tokenize(gts)
        res = tokenizer.tokenize(res)

        # Set up scorers
        if self.verbose:
            print '| Setting up scorers ...'
        scorers = [
            (Bleu(4), ["Bleu_1", "Bleu_2", "Bleu_3", "Bleu_4"]),
            (Meteor(),"METEOR"),
            (Rouge(), "ROUGE_L"),
            (Cider(), "CIDEr")
        ]

        # Compute scores
        output = {}
        for scorer, method in scorers:
            if self.verbose:
                print 'computing %s score...'%(scorer.method())
            score, scores = scorer.compute_score(gts, res)
            if type(method) == list:
                for sc, scs, m in zip(score, scores, method):
                    output[m] = sc
                    if self.verbose:
                        print "Calculated tIoU: %1.1f, %s: %0.3f" % (tiou, m, sc)
            else:
                output[method] = score
                if self.verbose:
                    print "Calculated tIoU: %1.1f, %s: %0.3f" % (tiou, method, score)
        return output

def main(args):
    # Call coco eval
    evaluator = ANETcaptions(ground_truth_filenames=args.references,
                             prediction_filename=args.submission,
                             tious=args.tious, verbose=args.verbose)
    evaluator.evaluate()

    # Output the results
    for metric in evaluator.scores:
        score = evaluator.scores[metric]
        print '| %s: %2.4f'%(metric, 100*score)

if __name__=='__main__':
    parser = argparse.ArgumentParser(description='Evaluate the results stored in a submissions file.')
    parser.add_argument('-s', '--submission', type=str,  default='sample_submission.json',
                        help='sample submission file for ActivityNet Captions Challenge.')
    parser.add_argument('-r', '--references', type=str, nargs='+', default='data/val_1.json,data/val_2.json',
                        help='reference files with ground truth captions to compare results against. delimited (,) str')
    parser.add_argument('--tious', type=float,  nargs='+', default=[0.3, 0.5, 0.7, 0.9],
                        help='Choose the tIoUs to average over.')
    parser.add_argument('-v', '--verbose', action='store_true',
                        help='Print intermediate steps.')
    args = parser.parse_args()

    main(args)
