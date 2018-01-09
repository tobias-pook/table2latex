#!/usr/bin/env python
import math
class rounding:
    """
    significant digits rounder
    """
    def __init__(self,sigdigits=2, negdigits=3, posdigits=3):
        self.sigdigits, self.negdigits, self.posdigits = sigdigits, negdigits, posdigits

    def latex(self, n, err1=None, err2=None):
        if err1 is None:
            return self.latexValue(n)
        elif err2 is None:
            return self.latexValueError(n, err1)
        else:
            return self.latexValueUpDownError(n, err1, err2)

    def html(self, n, err1=None, err2=None):
        if err1 is None:
            return self.htmlValue(n)
        elif err2 is None:
            return self.htmlValueError(n, err1)
        else:
            return self.htmlValueUpDownError(n, err1, err2)

    def latexValue(self, n):
        value, expo = self.sdr(n)
        if expo != 0:
            return '${0}\cdot10^{{{1}}}$'.format(value, expo)
        else:
            return '{0}'.format(value)

    def latexValueError(self, n, error):
        a, b, expo = self.sdr(n, error)
        if expo != 0:
            return '${0}\pm{1}\cdot10^{{{2}}}$'.format(a, b, expo )
        else:
            return '${0}\pm{1}$'.format(a, b)

    def latexValueSignificantly(self, n, error):
        a, b, expo = self.sdr(n, error)
        if expo != 0:
            return '${0}\cdot10^{{{1}}}$'.format(a, expo )
        else:
            return '{0}'.format(a)

    def latexValueUpDownError( self, n, up, down ):
        a, b, c, expo = self.sdr( n, up, down )
        if expo != 0:
            return '${0}^{{+{1}}}_{{-{2}}}\cdot10^{{{3}}}$'.format(a, b, c, expo)
        else:
            return '${0}^{{+{1}}}_{{-{2}}}$'.format(a, b, c)

    def htmlValue(self, n):
        value, expo = self.sdr(n)
        if expo != 0:
            return '{0}&sdot;10<sup>{1}</sup>'.format( value, expo )
        else:
            return '{0}'.format(value)

    def htmlValueError(self, n, error):
        a, b, expo = self.sdr( n, error )
        if expo != 0:
            return '{0}&plusmn;{1}&sdot;10<sup>{2}</sup>'.format(a, b, expo)
        else:
            return '{0}&plusmn;{1}'.format(a, b)

    def htmlValueUpDownError( self, n, up, down ):
        a, b, c, expo = self.sdr( n, up, down )
        if expo != 0:
            return '{0} <span style="position: relative; display: inline-block; line-height: 1; margin-right: .3em">&nbsp;<sup style="display: block; font-size: .5em; line-height: 1">+{1}</sup><sub style="display: block; font-size: .5em; line-height: 1">-{2}</sub></span>&sdot;10<sup>{3}</sup>'.format(a, b, c, expo)
        else:
            return '{0} <span style="position: relative; display: inline-block; line-height: 1; margin-right: .3em">&nbsp;<sup style="display: block; font-size: .5em; line-height: 1">+{1}</sup><sub style="display: block; font-size: .5em; line-height: 1">-{2}</sub></span>'.format(a, b, c)

    def sdr(self, *numbers):
        nonzerolist = [math.floor(math.log10(abs(f))) for f in numbers if f!=0]
        try:
            x=min(nonzerolist)
        except ValueError:
            return tuple(['0']*(len(numbers))+ [0])
        res=[]
        if x < -self.negdigits or x > self.posdigits:
            expo=int(x)
        else: expo=0
        roundto=int(x-expo-self.sigdigits+1)
        for f in numbers:
            g=1.* f/ (10**expo)
            if round(g,-roundto) == 10.0 and expo > 1:
                g= 1.
                expo+=1
            if g==0:
                s="0"
            elif roundto<0:
                s=("{0:."+str(int(-roundto))+"f}").format(g)
            else:
                s=str(int(round(g,-roundto)))
            res.append(s)
        res.append(expo)
        return tuple(res)
