#!/usr/bin/python

import os
import sys
import struct

def rword(bytes):
	return struct.unpack("<I", bytes)[0]
def rquad(bytes):
	return struct.unpack("<q", bytes)[0]
def rdouble(bytes):
	return struct.unpack("<d", bytes)[0]
def rsingle(bytes):
	return struct.unpack("<f", bytes)[0]

# Reads a flexible number from the bytes array and returns a tuple
# containing the number read and the number of bytes read.
def readFlexNumber(bytes, addr):
	number = 0
	shift = 0
	ptr = addr
	while True:
		num = ord(bytes[ptr])
		ptr += 1

		number |= (num & 0x7F) << shift
		shift += 7

		if num & 0x80:
			break
		if shift > 30:
			raise Exception("Flex number invalid or too large.")
	return (number, ptr - addr)

def readHeader(bytes, start):
	hsize = u32(bytes, start )  ; start +=  4
	# print "Header size (words): " + str(hsize)
	
	sections = []
	sectionsCount = hsize >> 1
	for section in range(0, sectionsCount):
		
		objcount = u32(bytes, start )  ; start +=  4
		address  = u32(bytes, start )  ; start +=  4
		
		sections += [(objcount, address)]
	return sections

def u32(data, off):
	hsize = rword( data[ off : off+4 ] )
	return hsize

def readKeys(bytes, keysSection):
	count, ptr = keysSection
	keys = []
	for i in range(0, count):
		
		length, size = readFlexNumber(bytes, ptr)
		ptr   += size

		keys.append( str(bytes[ptr : ptr + length]) )
		ptr += length
	return keys

def readObjects(bytes, objectsSection):
	count, ptr = objectsSection
	objects = []
	for i in range(0, count):
		class_idx, l = readFlexNumber( bytes, ptr) ;ptr += l
		start_idx, l = readFlexNumber( bytes, ptr) ;ptr += l
		size     , l = readFlexNumber( bytes, ptr) ;ptr += l

		objects.append( (class_idx, start_idx, size) )
		
	return objects

def readClasses(bytes, classSection):
	count, addr = classSection
	classes = []
	
	ptr     = addr
	
	for i in range(0, count):
		
		length, l = readFlexNumber(bytes, ptr);		ptr += l
		
		tp = ord(bytes[ptr]);		ptr += 1
		
		unknown = None
		assert(tp in [0x80, 0x81])
		if tp == 0x81:
			unknown = rword(bytes[ptr : ptr + 4])
			ptr += 4
			print 'readClasses: Mystery value:', unknown, '(',

		className = str(bytes[ptr : ptr + length - 1])
		classes.append( className )

		if unknown:
			print classes[-1], ')'

		ptr += length

	return classes

def readValues(bytes, valuesSection, debugKeys = []):
	count, addr = valuesSection
	values = []
	ptr = addr
	
	for i in range(0, count):
		key_idx, l = readFlexNumber(bytes, ptr);	ptr += l

		encoding = ord(bytes[ptr]);	ptr += 1

		value = None
		
		if encoding == 0x00:	# single byte
			value = ord(bytes[ptr]);	ptr += 1
			
		elif encoding == 0x01:	# short
			value = struct.unpack("<H", bytes[ptr : ptr + 2])[0]
			ptr += 2
			
		elif encoding == 0x03:  # 8 byte integer
			value = rquad(bytes[ptr:ptr+8])
			ptr += 8
			
		elif encoding == 0x04:
			value = False
			
		elif encoding == 0x05:	# true
			value = True
			
		elif encoding == 0x06:	# word
			# if len(debugKeys):
				# print "Found encoding with 0x6", debugKeys[key_idx]
			value = rsingle(bytes[ptr:ptr+4])
			ptr += 4
			
		elif encoding == 0x07:	# floating point
			value = rdouble(bytes[ptr:ptr+8])
			ptr += 8
			
		elif encoding == 0x08:	# string
			length, l = readFlexNumber(bytes, ptr);		ptr += l
			
			if length and ord(bytes[ptr]) == 0x07:
				if length == 17:
					value = struct.unpack("<dd", bytes[ptr + 1 : ptr + 17])
				elif length == 33:
					value = struct.unpack("<dddd", bytes[ptr + 1 : ptr + 33])
				else:
					raise Exception("Well this is weird.")
			else:
				value = str(bytes[ptr : ptr + length])
			ptr += length
			
		elif encoding == 0x09:	# nil?
			value = None
			
		elif encoding == 0x0A:	# object
			value = '@' + str(rword(bytes[ptr:ptr+4])) #object is stored as a 4 byte index.
			ptr += 4
		else:
			# print "dumping classes:", globals()['classes']
			print "dumping keys:" #, globals()['keys']
			for n, key in enumerate(globals()['keys']):
				print "%X\t%X\t%s" % (n, (n | 0x80), key)
			raise Exception("Unknown value encoding (key %d idx %d addr %d): " % (key_idx, i, ptr-1) + str(encoding))
		
		values.append( (key_idx, value, encoding) )
		
	return values

def fancyPrintObjects(nib, prefix="", showencoding=False):
	objects, keys, values, classes = nib
	
	for o_idx, object in enumerate(objects):
		
		#print object
		classname  = classes[ object[0] ]
		obj_values = values[ object[1]: object[1] + object[2] ]

		print prefix + "%3d: %s" % (o_idx, classname)

		for v in obj_values:
			# print v
			k_str = keys[ v[0] ]
			v_str = str(  v[1] )

			printSubNib =	k_str == 'NS.bytes' and \
					len(v_str) > 40 and \
					v_str.startswith('NIBArchive')

			if printSubNib:
				print prefix + '\t' + k_str + " = Encoded NIB Archive"
				nib = readNibSectionsFromBytes(v[1])
				fancyPrintObjects(nib, prefix + "\t", showencoding)

			else: # Boring regular data.
				Encoding =  '(' + str(v[2]) + ')' if showencoding else ''
				
				print prefix + '\t' + k_str + ' =' + Encoding , v_str

			# if k_str == 'NS.bytes' and len(v_str) > 200:
			# 	with open('embedded.nib', 'wb') as f:
			# 		f.write(v[1])

def readNibSectionsFromBytes(bytes):
	sections = readHeader( bytes, 14)
	# print sections
	
	assert len(sections) == 4
	
	classes = readClasses( bytes, sections[3] )
	# print classes
	
	objects = readObjects( bytes, sections[0] )
	# print objects
	
	keys    = readKeys(    bytes, sections[1] )
	# print keys
	
	values  = readValues(  bytes, sections[2] )
	# print values
	
	return (objects, keys, values, classes)

def ibdump( filename, showencoding=None ):
	with open( filename, 'rb' ) as file:
		filebytes = file.read()

	pfx     = filebytes[    : 10]
	print "Prefix: " + pfx

	headers = filebytes[ 10 : 10+4]
	headers = rword(headers)
	
	print "Headers: " + str(headers)

	if str(pfx) != "NIBArchive":
		print "\"%s\" is not a NIBArchive file." % (filename)
		return

	nib = readNibSectionsFromBytes( filebytes )
	fancyPrintObjects( nib, showencoding=showencoding )

if __name__ == '__main__':
	
	if len(sys.argv) <> 2:
		print "ibdump - dumps the contents of a NIB file in a readable format\n" \
		      "~~~~~~\n" \
		      "usage: \tibdump <*.nib>\n"
		
	else:
		ibdump( sys.argv[1], True )
