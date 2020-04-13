/*===========================================================================*\
 * Experimental implementation of MFCC.
 * (c) Vail Systems. Joshua Jung and Ben Bryan. 2015
 *
 * This code is not designed to be highly optimized but as an educational
 * tool to understand the Mel-scale and its related coefficients used in
 * human speech analysis.
\*===========================================================================*/
const dct = require('dct');
const numpy = require('numjs');
const sigproc = require('./sigproc');

module.exports = {
  /*
   * Given a set of amplitudes, estimates the power for those amplitudes.
   */
  powerSpectrum: powerSpectrum,
  /*
   * Converts from hertz to the Mel-scale. Used by constructFilterBank.
   *
   * Based on the concept that human perception of an equidistant pitch decreases as
   * pitch increases.
   */
  hzToMels: hzToMels,
  /*
   * Inverse of hzToMels.
   */
  melsToHz: melsToHz,
  /*
   * Returns a filter bank with bankCount triangular filters distributed according to the mel scale.
   *
   * Focused specifically on human speech (300 hz - 8000 hz)
   *
   * Recommended values for u-law 8000 hz:
   *
   *   - fftSize == 64 (128 bin FFT)
   *   - bankCount == 31
   *   - Low Frequency == 200
   *   - High Frequency == 3500
   */
  constructMelFilterBank: constructMelFilterBank,
  construct: construct
};

// function getCols(matrix, col) {
//   let column = [];
//   for (let i = 0; i < matrix.length; i++) {
//     for (let ii = 0; ii < col; ii++)
//       column.push(matrix[i][ii]);
//   }
//   return column;
// }

// function mfcc(
//   signal = [], samplerate = 16000,
//   winlen = 0.025, winstep = 0.01,
//   numcep = 13, nfilt = 26,
//   nfft = 512, lowfreq = 0,
//   highfreq = null, preemph = 0.97,
//   ceplifter = 22, appendEnergy = true,
//   winfunc = (x) => [...Array(x)].fill(1)) {

//   highfreq = highfreq || samplerate / 2
//   signal = sigproc.preemphasis(signal, preemph)
//   frames = sigproc.framesig(signal, winlen * samplerate, winstep * samplerate, winfunc)
//   pspec = sigproc.powspec(frames, nfft)
//   energy = numpy.sum(pspec, 1) // this stores the total energy in each frame
//   energy = numpy.where(energy == 0, numpy.finfo(float).eps, energy) // if energy is zero, we get problems with log

//   fb = get_filterbanks(nfilt, nfft, samplerate, lowfreq, highfreq)
//   feat = numpy.dot(pspec, fb.T) // compute the filterbank energies
//   feat = numpy.where(feat == 0, numpy.finfo(float).eps, feat) // if feat is zero, we get problems with log


//   let fbank_val = fbank(signal, samplerate, winlen, winstep, nfilt, nfft, lowfreq, highfreq, preemph, winfunc);
//   feat = fbank_val.feat;
//   energy = fbank_val.energy;

//   feat = numpy.log(feat);
//   feat = getCols(dct(feat, type = 2, axis = 1, norm = 'ortho'), numcep);
//   construct.length(feat.length())
//   feat = lifter(feat, ceplifter);
//   if (appendEnergy)
//     feat.forEach(x => x[0] = numpy.log(energy));
//   return feat
// }

// mfcc();

function construct(fftSize, bankCount, lowFrequency, highFrequency, sampleRate) {
  if (!fftSize) throw Error('Please provide an fftSize');
  if (!bankCount) throw Error('Please provide a bankCount');
  if (isNaN(lowFrequency) || lowFrequency < 0) throw Error('Please provide a low frequency cutoff.');
  if (!highFrequency) throw Error('Please provide a high frequency cutoff.');
  if (!sampleRate) throw Error('Please provide a valid sampleRate.');

  var filterBank = constructMelFilterBank(fftSize, bankCount, lowFrequency, highFrequency, sampleRate);

  /**
   * Perform a full MFCC on a FFT spectrum.
   *
   * FFT Array passed in should contain frequency amplitudes only.
   *
   * Pass in truthy for debug if you wish to return outputs of each step (freq. powers, melSpec, and MelCoef)
   */
  return function (fft, debug) {
    if (fft.length != fftSize)
      throw Error('Passed in FFT bins were incorrect size. Expected ' + fftSize + ' but was ' + fft.length);

    var //powers = powerSpectrum(fft),
      melSpec = filterBank.filter(fft),
      melSpecLog = melSpec.map(Math.log),
      melCoef = dct(melSpecLog).slice(0, 13).map(function (c, index) {
        // 'ortho' normalization as in scipy.fftpack.dct (Type II)
        // https://docs.scipy.org/doc/scipy/reference/generated/scipy.fftpack.dct.html
        const norm = 1 / Math.sqrt(2 * melSpecLog.length);
        if (index === 0) return c * norm / Math.sqrt(2);
        return c * norm;
      }),
      power = melCoef.splice(0, 1);

    return debug ? {
      melSpec: melSpec,
      melSpecLog: melSpecLog,
      melCoef: melCoef,
      filters: filterBank,
      power: power
    } : melCoef;
  }
}

function constructMelFilterBank(fftSize, nFilters, lowF, highF, sampleRate) {
  var bins = [],
    fq = [],
    filters = [];

  var lowM = hzToMels(lowF),
    highM = hzToMels(highF),
    deltaM = (highM - lowM) / (nFilters + 1);

  // Construct equidistant Mel values between lowM and highM.
  for (var i = 0; i < nFilters + 2; i++) {
    // Get the Mel value and convert back to frequency.
    // e.g. 200 hz <=> 401.25 Mel
    fq[i] = melsToHz(lowM + (i * deltaM));

    // Round the frequency we derived from the Mel-scale to the nearest actual FFT bin that we have.
    // For example, in a 64 sample FFT for 8khz audio we have 32 bins from 0-8khz evenly spaced.
    bins[i] = Math.floor((fftSize + 1) * fq[i] / (sampleRate / 2));
  }

  // Construct one cone filter per bin.
  // Filters end up looking similar to [... 0, 0, 0.33, 0.66, 1.0, 0.66, 0.33, 0, 0...]
  for (var i = 0; i < bins.length - 2; i++) {
    filters[i] = [];
    for (var f = 0; f < fftSize; f++) {
      // Right, outside of cone
      if (f > bins[i + 2]) filters[i][f] = 0.0;
      // Right edge of cone
      else if (f > bins[i + 1]) filters[i][f] = 1.0 - ((f - bins[i + 1]) / (bins[i + 2] - bins[i + 1]));
      // Peak of cone
      else if (f == bins[i + 1]) filters[i][f] = 1.0;
      // Left edge of cone
      else if (f >= bins[i]) filters[i][f] = 1.0 - (bins[i + 1] - f) / (bins[i + 1] - bins[i]);
      // Left, outside of cone
      else filters[i][f] = 0.0;
    }
  }

  // Here we actually apply the filters one by one. Then we add up the results of each applied filter
  // to get the estimated power contained within that Mel-scale bin.
  //
  // First argument is expected to be the result of the frequencies passed to the powerSpectrum
  // method.
  return {
    filters: filters,
    lowMel: lowM,
    highMel: highM,
    deltaMel: deltaM,
    lowFreq: lowF,
    highFreq: highF,
    bins: bins,
    filter: function (freqPowers) {
      var ret = [];

      filters.forEach(function (filter, fIx) {
        var tot = 0;
        freqPowers.forEach(function (fp, pIx) {
          tot += fp * filter[pIx];
        });
        ret[fIx] = tot;
      });
      return ret;
    }
  };
}

function melsToHz(mels) {
  return 700 * (Math.pow(10, (mels / 2595)) - 1);
}

function hzToMels(hertz) {
  return 2595 * Math.log10(1 + hertz / 700);
}

/**
 * Estimate the power spectrum density from FFT amplitudes.
 */
function powerSpectrum(amplitudes) {
  var N = amplitudes.length;

  return amplitudes.map(function (a) {
    return (a * a) / N;
  });
}