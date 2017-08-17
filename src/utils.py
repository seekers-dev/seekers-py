import math

def foldr(f,a,xs):
  for x in xs:
    a = f(a,x)
  return a

def foldr1(f,xs):
  return foldr(f,xs[0],xs[1:])

def flatten(nested):
  for xs in nested:
    for x in xs:
      yield x

def bump(r):
  return math.exp(1 / (r**2 - 1)) if r < 1 else 0
