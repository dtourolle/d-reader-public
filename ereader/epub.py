from html.parser import HTMLParser
import re
from html import unescape
from urllib.parse import unquote

import xmltodict
from zipfile import ZipFile

from PIL import Image, ImageFont, ImageOps
import PIL.ImageOps as ops
from io import BytesIO
from hyphen import Hyphenator,dictools
from textwrap2 import wrap
import textwrap
from collections import OrderedDict
import threading
from typing import Dict, Any, List

settings = {'canvas_shape':(1072, 1448),'font_size':42,'background':255,'margin':80,'line_spacing':60,'list_spacing':0,'text_width':100}


class HTMLtoLines(HTMLParser):
    para = {"p", "div"}
    inde = {"q", "dt", "dd", "blockquote"}
    pref = {"pre"}
    bull = {"li"}
    hide = {"script", "style", "head"}
    # hide = {"script", "style", "head", ", "sub}

    def __init__(self):
        HTMLParser.__init__(self)
        self.text = [""]
        self.imgs = {}
        self.ishead = False
        self.isinde = False
        self.isbull = False
        self.ispref = False
        self.ishidden = False
        self.idhead = set()
        self.idinde = set()
        self.idbull = set()
        self.idpref = set()

    def handle_starttag(self, tag, attrs):
        if re.match("h[1-6]", tag) is not None:
            self.ishead = True
        elif tag in self.inde:
            self.isinde = True
        elif tag in self.pref:
            self.ispref = True
        elif tag in self.bull:
            self.isbull = True
        elif tag in self.hide:
            self.ishidden = True
        elif tag == "sup":
            self.text[-1] += "^{"
        elif tag == "sub":
            self.text[-1] += "_{"
        elif tag == "image":
            for i in attrs:
                if i[0] == "xlink:href":
                    
                    self.text.append("[IMG:{}]".format(len(self.imgs)))
                    self.imgs["[IMG:{}]".format(len(self.imgs))]=unquote(i[1])

    def handle_startendtag(self, tag, attrs):
        if tag == "br":
            self.text += [""]
        elif tag in {"img", "image"}:
            for i in attrs:
                if (tag == "img" and i[0] == "src") or (tag == "image" and i[0] == "xlink:href"):
                    
                    self.text.append("[IMG:{}]".format(len(self.imgs)))
                    self.imgs["[IMG:{}]".format(len(self.imgs))]=unquote(i[1])
                    
                    self.text.append("")

    def handle_endtag(self, tag):
        if re.match("h[1-6]", tag) is not None:
            self.text.append("")
            self.text.append("")
            self.ishead = False
        elif tag in self.para:
            self.text.append("")
        elif tag in self.hide:
            self.ishidden = False
        elif tag in self.inde:
            if self.text[-1] != "":
                self.text.append("")
            self.isinde = False
        elif tag in self.pref:
            if self.text[-1] != "":
                self.text.append("")
            self.ispref = False
        elif tag in self.bull:
            if self.text[-1] != "":
                self.text.append("")
            self.isbull = False
        elif tag in {"sub", "sup"}:
            self.text[-1] += "}"
        elif tag == "image":
            self.text.append("")

    def handle_data(self, raw):
        if raw and not self.ishidden:
            if self.text[-1] == "":
                tmp = raw.lstrip()
            else:
                tmp = raw
            if self.ispref:
                line = unescape(tmp)
            else:
                line = unescape(re.sub(r"\s+", " ", tmp))
            self.text[-1] += line
            if self.ishead:
                self.idhead.add(len(self.text)-1)
            elif self.isbull:
                self.idbull.add(len(self.text)-1)
            elif self.isinde:
                self.idinde.add(len(self.text)-1)
            elif self.ispref:
                self.idpref.add(len(self.text)-1)

    def get_lines(self, width=0):
        text = []
        if width == 0:
            return self.text,self.imgs
        for n, i in enumerate(self.text):
            if n in self.idhead:
                text += [i.rjust(width//2 + len(i)//2)] + [""]
            elif n in self.idinde:
                text += ["   "+j for j in textwrap.wrap(i, width - 3)] + [""]
            elif n in self.idbull:
                tmp = textwrap.wrap(i, width - 3)
                text += [" - "+j if j == tmp[0] else "   "+j for j in tmp] + [""]
            elif n in self.idpref:
                tmp = i.splitlines()
                wraptmp = []
                for line in tmp:
                    wraptmp += [j for j in textwrap.wrap(line, width - 6)]
                text += ["   "+j for j in wraptmp] + [""]
            else:
                text += textwrap.wrap(i, width) + [""]
        return text, self.imgs



class FixSizeOrderedDict(OrderedDict):
    def __init__(self, *args, max=0, **kwargs):
        """This is a dict with a fixed size and order. It is used as a 
        "circular buffer" for the pages which are pre-rendered. The key 
        is the current page number.

        Args:
            max (int, optional): The total size of the buffer, if zero there is no limit. Defaults to 0.
        """        
        self._max = max
        super().__init__(*args, **kwargs)

    def __setitem__(self, key, value):
        OrderedDict.__setitem__(self, key, value)
        if self._max > 0:
            if len(self) > self._max:
                self.popitem(False)

class ebook:
    
    def __init__(self,file:str,buffer:int=7):
        """Create an ebook object, will load it from the epub file.

        Args:
            file (str): path to the file.
            buffer (int, optional): Number of pre-rerendered pages. Defaults to 7.
        """        
        self.input_zip = file
        input_zip=ZipFile(self.input_zip)
        self.components = {name: input_zip.read(name) for name in input_zip.namelist()}
        self.author,self.title,self.dates,self.cover, self.language = self.extract_metadata().values()
        self.organisation = self.get_organisation()
        self.font = "/usr/share/fonts/truetype/ttf-dejavu/DejaVuSans.ttf" # "/usr/share/fonts/truetype/noto/NotoMono-Regular.ttf"#
        self.location_info = {'page':0,'doc':list(self.organisation)[0],'line':0}
        self.view_page = 0
        self.current_doc = None
        self.buffer = buffer
        self.page_buffer = FixSizeOrderedDict(max=buffer+1)
        self.chapter_lines = []
        self.language = self.clean_language()
        print("Using language:",self.language)
        self.Hyphenator = Hyphenator(self.language)
        self.page_starts = {}
        self.get_current_doc()
        self.prepare_current_doc()
        self.gen_buffer()
        self.render_thread = None

    def clean_language(self)->str:
        """Some epubs have a language in the meta-data, some do not, there seems to also
        be no standard in how languages are abbreviated. Since this will likely only be used
        for English, French and German ebooks, catch the most common cases and if not assume
        english. This is only really needed for hyphenation.

        Returns:
            str: a valid language string.
        """        
        print("checking language for hyphenation",self.language)
        self.language = self.language.strip()
        if self.language in dictools.LANGUAGES:
            return self.language
        
        if self.language in ['fr','FR','Fr']:
            return 'fr_FR'
        if self.language in ['de','DE','De']:
            return 'de_DE'
        
        return 'en_US'

    def gen_buffer(self):
        """generate the buffer of pre-rendered pages for fist time.
        """        
        for i in range(self.buffer):
            print("Buffer_stuff",i)
            self.render_pages(settings)
            
            
    def current_page(self)->Image:
        """get the current page buffer.

        Returns:
            Image: The current page from the buffer.
        """        
        return self.page_buffer[self.view_page]
        
    def next_page(self)->Image:
        """Increment the page buffer and return the current page if possible. If
        not possible it will spawn new threads to render the page and return a page
        on completion. Some checks are made to ensure new threads are only spawned
        when no rendering threads exists.

        Returns:
            Image: the current page after the increment.
        """        
        if self.location_info['page']-self.view_page <7:
            print("rendering pages at middle of buffer:",self.location_info['page']-self.view_page)
            if self.render_thread is None:
                self.render_thread = threading.Thread(target=self.render_n_pages, args=(settings,7-self.location_info['page']+self.view_page))
                self.render_thread.start()
        elif self.view_page in self.page_buffer is False:
            print("rendering pages as buffer is problematic")
            if self.render_thread is None:
                self.render_thread = threading.Thread(target=self.render_n_pages, args=(settings,self.location_info['page']+self.view_page))
                self.render_thread.start()
                self.render_thread.join()
            return self.page_buffer[self.view_page]


        self.view_page+=1
        try:
            return self.page_buffer[self.view_page]
        except:
            if self.render_thread is None:
                self.render_pages(settings)
                return self.page_buffer[self.view_page]
            else:
                
                return self.page_buffer[list(self.page_buffer)[-1]]


    def render_page_threaded(self,settings:Dict[str, Any]):
        """Render method for the threads. Allowing settings with different page numbers.

        Args:
            settings (Dict[str, Any]): Settings for the renderer.
        """        
        self.render_pages(settings)
        self.render_thread=None




    def previous_page(self)->Image:
        """Return the previous page and increment the buffer backwards.

        Returns:
            Image: The previous page.
        """        
        self.view_page-=1
        print(self.view_page)
        if self.view_page <0:
            self.view_page = 0
        print(self.view_page , list(self.page_buffer.keys()))
        if self.view_page in list(self.page_buffer.keys()):
            print("it is stored reuse")
            return self.page_buffer[self.view_page]
        else:
            print("it not stored recreate")
            self.location_info['line']= self.page_starts[self.view_page][0]
            self.location_info['doc']= self.page_starts[self.view_page][1]
            self.location_info['page'] = self.view_page
            self.get_current_doc()
            self.prepare_current_doc()
            self.render_pages(settings)
            
            return self.page_buffer[self.view_page]

    def render_n_pages(self,settings:Dict[str, Any],n:int):
        """Render an arbitrary number of pages ahead and store them in the buffer.

        Args:
            settings (Dict[str, Any]): The layout settings for the pages.
            n (int): number of pages to be rendered.
        """        
        for i in range(n):
            self.render_pages(settings)
        self.render_thread=None

    
    def extract_metadata(self)->Dict[str, str]:
        """Extract metadata about EPUB from the file.

        Returns:
            Dict[str, str]: The metadata in a dictionary.
        """
        opf = [i for i in self.components if '.opf' in i][0]
        contents_decoded=xmltodict.parse(self.components[opf].decode("utf-8"))
        metadata = contents_decoded['package']['metadata']
        author_info = metadata['dc:creator']

        if type(author_info) is list:
            author=[x['#text'] for x in author_info]
        elif type(author_info) is str:
            author=author_info
        else:
            try:
                author=author_info['#text']
            except:
                author = 'Unknown'
        title=metadata['dc:title']
        date_info = metadata.get('dc:date','')
        if type(date_info) is str:
            dates = {'published':date_info}
        else:
            dates = {x['@opf:event']:x['#text'] for x in date_info}
        language = metadata.get('dc:language',{})

        meta = metadata.get('meta')
        cover = None
        if type(meta) is list:
            for m in meta:
                c = m.get('cover')
        else:
            cover = meta.get('@content')

        return {'author':author,'title':title,'dates':dates,'cover':cover,'language':language}
    
    def get_current_doc(self):
        """Load the current sub document of the EPUB into a buffer dor processing into pages.
        """        
        parser = HTMLtoLines()
        content = self.components[self.organisation[self.location_info['doc']]].decode("utf-8")
        parser.feed(content)
        self.current_doc=parser.get_lines()
        
    def get_organisation(self)->Dict[str,str]:
        """Using the opf determine the structure of the ebook.

        Returns:
            Dict[str,str]: The structure (a dict of all sub-documents with keys which can determine the order in the book)
        """
        opf = [i for i in self.components if '.opf' in i][0]
        opf_location = '/'.join(opf.split('/')[:-1])
        
        contents_decoded=xmltodict.parse(self.components[opf].decode("utf-8"))
        manifest = {a['@id']:a['@href'] for a in contents_decoded['package']['manifest']['item']}

        entries = [x['@idref'] for x in   contents_decoded['package']['spine']['itemref']]
        
        organisation = {entry:manifest[entry] for entry in entries}
        for entry,path in organisation.items():
            if self.components.get(path) is None:
                organisation[entry] = opf_location +'/'+path
        
        return(organisation)
    
    
    def render_pages(self,settings:Dict[str,Any]):
        """Using the stored data of the EPUB and the rendering settings generate an page of the book as an image.
        Store the page in the buffer, and store the line and sub-document in a look up for fast reverse scrolling.


        Args:
            settings (Dict[str,Any]): The settings for the renderer.
        """        
        canvas = Image.new('L',settings['canvas_shape'], color=0)

        font = ImageFont.truetype(self.font , settings['font_size'],layout_engine=ImageFont.LAYOUT_RAQM)


        current_line = self.location_info['line']
        on_page = True
        line_spacing = settings['line_spacing']
        x_cursor=settings['margin']
        y_cursor = settings['margin']
        self.page_buffer[self.location_info['page']]=canvas
        print("page: ",self.location_info)
        while on_page:
            #print(current_line,self.location_info)
            if len(self.chapter_lines) > current_line:
                my_line = self.chapter_lines[current_line]
            else:
                self.page_starts[self.location_info['page']]=(self.location_info['line'],self.location_info['doc'])
                self.location_info['line']=0
                new_doc=list(self.organisation).index(self.location_info['doc'])+1
                self.location_info['doc']=list(self.organisation)[new_doc]
                self.get_current_doc()
                self.prepare_current_doc()
                
                self.location_info['page']+=1
                #self.render_pages(settings)
                return
            if type(my_line) is str:
                line_mask = font.getmask2(my_line,mode='L' )[0]
                dy = line_spacing - line_mask.size[1]
                canvas.paste(line_mask,(x_cursor,y_cursor,x_cursor+line_mask.size[0],y_cursor+line_mask.size[1]))
                
            else:
                print("Page as image")
                img = self.chapter_lines[current_line]
                x_space = (settings['canvas_shape'][0] - img.size[0])//2
                avail_space = (settings['canvas_shape'][1]-y_cursor - settings['margin'])
                if avail_space < img.size[0]:
                    self.page_starts[self.location_info['page']]=(self.location_info['line'],self.location_info['doc'])
                    self.location_info['line']=current_line
                    self.location_info['page']+=1
                    return 
                canvas.paste(img,(x_space,y_cursor,x_space+img.size[0],y_cursor+img.size[1]))
                y_cursor+=img.size[1]+line_spacing
                current_line+=1


            y_cursor+=line_spacing
            current_line+=1
            
            if y_cursor > settings['canvas_shape'][1]-settings['margin']:
                self.page_starts[self.location_info['page']]=(self.location_info['line'],self.location_info['doc'])
                self.location_info['line']=current_line
                self.location_info['page']+=1
                return
            if current_line >= len(self.chapter_lines):
                self.page_starts[self.location_info['page']]=(self.location_info['line'],self.location_info['doc']) 
                new_doc=list(self.organisation).index(self.location_info['doc'])+1
                if new_doc < len(list(self.organisation)):
                    self.location_info['line']=0
                    self.location_info['doc']=list(self.organisation)[new_doc]
                    self.get_current_doc()
                    self.prepare_current_doc()
                #self.page_starts[self.location_info['page']]=(self.location_info['line'],self.location_info['doc'])
                self.location_info['page']+=1
                return
                    
                
    
    def prepare_current_doc(self,line_width=42):
        """This function splits up the sub document into lines which should
        fit on the page. If a line would go over the page a hyphenator is used
        to split the word at the end according to language based rules.

        Args:
            line_width (int, optional): The expected number of characters per line. Defaults to 42.
        """        
        self.chapter_lines=[]
        for segment in self.current_doc[0]:
            if '[IMG:' in segment:#does this segment contain an image
                if segment[-1] == ']': # is it only and image?
                    #then lets load it and add it to the lines
                    self.chapter_lines.append(self.load_image(segment))

            else:
                try: 
                    lines = wrap(segment, width=line_width, use_hyphenator=self.Hyphenator)
                except:
                    segment=segment.replace('\n','')
                    lines = textwrap.wrap(segment,width=line_width)
                self.chapter_lines += lines
    
    def load_image(self,image_key:str)->Image:
        """Based upon the image key in a sub-document load the image to be displayed.
        As E-ink is grayscale, and on top of the resolution of the images vs the screen
        is going to be really random as no one seems to store real DPIs, rescale the 
        image to fit on the screen and perform contrast enhancement to make it clearer
        in greyscale.

        Args:
            image_key (str): The image id in the sub-document.

        Returns:
            Image: The image made pretty for the E-ink
        """        
        doc_location = self.organisation[self.location_info['doc']].split('/')[:-1]
        
        image_location = '/'.join(doc_location+[self.current_doc[1].get(image_key)])
        
        if image_location:
            image_data = self.components[image_location]
            fh = BytesIO(image_data)
            img = ImageOps.invert(Image.open(fh).convert('L'))
            if img.size[0] > 1072-80 or img.size[0] > 1448-80:
                print('bigger')
                img.thumbnail((1072-80, 1448-80),Image.ANTIALIAS)
            elif img.size[0] > 1072-80 and img.size[0]/img.size[1]>0.5:
                img =img.resize((img.size[0]*4, img.size[1]*4))
                img.thumbnail((1072-80, 1448-120),Image.ANTIALIAS)
            else:    
                img =img.resize((img.size[0]*4, img.size[1]*4))
                img.thumbnail((1072-80, 1448-120),Image.ANTIALIAS)
            return ops.autocontrast(img,cutoff=3)
        else:
            return ''