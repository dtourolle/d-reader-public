
from IT8951 import constants
from IT8951.display import AutoEPDDisplay
import os
from glob import glob
from ebooklib import epub

from PIL import Image, ImageDraw, ImageFont, ImageOps
from copy import deepcopy
import textwrap
import controls
import shelve
from time import sleep
import threading
import epub as epb


class master_program:

    def __init__(self,submodules):
        self.submodules = submodules
        self.display = AutoEPDDisplay(vcom=-2.06, rotate="CW", spi_hz=24000000)
        self.ebook_list = []
        self.refersh_ebook_list()

        self.settings = {'rotation':'CCW','canvas_shape':(1072, 1448),'font_size':42,'background':255,'margin':40,'line_spacing':15,'list_spacing':25,'text_width':44,'number_of_lines':27,'state':'book_menu','selected_book':None,'current_read_path':None}
        self.settings['state'] = 'book_menu'
        self.settings_file = '/home/pi/ereader/settings.db' 
        self.input_handler = controls.check_gpio()
        self.load_settings()


    def save_settings(self,names=None):

        if names is None:
            keys = list(self.settings.keys())
        with shelve.open(self.settings_file) as db:
            for key in keys:
                db[key]=self.settings[key]

    def load_settings(self,names=None):
        if names is None:
            keys = list(self.settings.keys())
        with shelve.open(self.settings_file) as db:
            for key in keys:
                self.settings[key]=db.get(key,self.settings[key])

    def launch(self):
        with shelve.open(self.settings_file) as db:
            try:
                self.settings['state'] = db['state']
            except:
                self.settings['state'] = 'book_menu'
                db['state'] = 'book_menu'
        self.state_manager()

    def refersh_ebook_list(self):
        self.ebook_list = []
        files = glob("/home/pi/ebooks/*.epub") + glob("/home/pi/ebooks/*.EPUB") + glob("/home/pi/ebooks/*.txt")
        files.sort(key=os.path.getmtime)
        for f in files:
            ending = f.split('.')[1]
            
            
            if ending != 'txt':
                book = epub.read_epub(f)
                title = book.get_metadata('DC', 'title')
                while type(title) is not str:
                    title = title[0]

                creator = book.get_metadata('DC', 'creator')
                while type(creator) is not str and creator is not None:
                    creator = creator[0]
                if creator is None:
                    creator = 'Unerkannt'
                entry={'path':f,'title':title,'creator':creator}
                self.ebook_list.append(entry)
            else:
                title = f.split('/')[-1]
                while type(title) is not str:
                    title = title[0]

                creator = 'unknown'
                while type(creator) is not str and creator is not None:
                    creator = creator[0]
                if creator is None:
                    creator = 'Unerkannt'
                entry={'path':f,'title':title,'creator':creator}
                self.ebook_list.append(entry)

    def book_menu(self):
        self.refersh_ebook_list()
        self.settings['state']='book_menu'
        titles = [entry['title']+': von '+ entry['creator'] for entry in self.ebook_list]
        def update_display():
            screen = display_list(titles,self.settings)
            self.display.frame_buf.paste(screen, (0,0))
            self.display.draw_full(constants.DisplayModes.GC16)
        update_display()
        while True:
            changed = False
            active_element = self.settings.get('active',None)

            key = self.input_handler.read_out()
            if key is not None:
                changed=True
                if active_element is None:
                    if key is 'down':
                        self.settings['active']=0
                    elif key is 'up':
                        self.settings['active']=len(titles)-1

                else:
                    if key is 'down':
                        self.settings['active']+=1
                        if self.settings['active']==len(titles):
                            self.settings['active'] = 0
                    elif key is 'up':
                        self.settings['active']-=1
                        if self.settings['active']<0:
                            self.settings['active'] = len(titles)-1
                if key is 'right' and active_element is not None:
                    self.settings['selected_book'] = self.ebook_list[active_element]
                    self.settings['active'] = None
                    self.settings['current_read_path'] = self.settings['selected_book']['path']
                    return 'reader_app'
                if key is 'power':
                    return 'quit'

            if changed:
                update_display()
                changed = False
            sleep(0.1)

    def quit(self):
        self.save_settings()
        self.input_handler.stop()
        screen = Image.open('/home/pi/ebooks/background.jpg').convert('LA').rotate(90, expand=True)
        print(screen.size)
        #screen=screen.rotate(90)
        self.display.frame_buf.paste(screen, (0,0))
        self.display.draw_full(constants.DisplayModes.GC16)
        os.system("sudo shutdown -P now")
        exit()

    def state_manager(self):
        while True:
            print(self.settings['state'])
            test_state = getattr(self, self.settings['state'])()
            if test_state is 'quit':
                self.quit()
            else:
                self.settings['state'] = test_state

            sleep(0.01)

    def reader_app(self):
        canvas = Image.new('L',self.settings['canvas_shape'], color=0)
        draw = ImageDraw.Draw(canvas)
        font_normal = ImageFont.truetype("/usr/share/fonts/truetype/ttf-dejavu/DejaVuSans.ttf", self.settings['font_size'],layout_engine=ImageFont.LAYOUT_RAQM)
        draw.text((100, 300), 'Loading Book...', font=font_normal, fill=255)
        self.display.frame_buf.paste(canvas.rotate(180), (0,0))
        self.display.draw_full(constants.DisplayModes.GC16)

        path = self.settings.get('current_read_path',None)
        whole_text=''
        if path is None:
            return 'book_menu'
        
        ebook = epb.ebook(self.settings['selected_book']['path'])
        if os.path.exists(self.settings['selected_book']['path']+'_reader_data.db')==False:
            pass#ebook.gen_buffer()
        else:
            print("loaded buffer from file")
        with shelve.open(self.settings['selected_book']['path']+'_reader_data') as db:
            ebook.view_page = db.get('view_page',ebook.view_page)
            ebook.location_info    = db.get('location_info',ebook.location_info)
            ebook.page_buffer = db.get('page_buffer',ebook.page_buffer)
            ebook.page_starts = db.get('page_starts',ebook.page_starts)
        ebook.get_current_doc()
        ebook.prepare_current_doc()
        
        self.settings['current_read_path'] = self.settings['selected_book']['path']+'_reader_data'
        #screen=display_list(src_lines[line:line+self.settings['number_of_lines']],{'rotation':'CW','canvas_shape':(1072, 1448),'font_size':42,'background':255,'margin':40,'line_spacing':10,'list_spacing':0,'text_width':100})
        #self.display.frame_buf.paste(screen, (0,0))
        #self.display.draw_full(constants.DisplayModes.GC16)
        page_size=[0,0]
        old_page_size=0
        changed = True
        print(list(ebook.page_buffer.keys()))
        new_screen = ebook.current_page()
        while True:
  
            direction = 0
            key = self.input_handler.read_out()
            if key is not None:
                changed=True

                if key is 'down':
                    #line -= self.settings['number_of_lines']
                    direction =-1
                elif key is 'up':
                    direction=1
                    # line += self.settings['number_of_lines']

                if key is 'left':
                    with shelve.open(self.settings['selected_book']['path']+'_reader_data') as db:
                        db['view_page']=ebook.view_page    
                        db['location_info']=ebook.location_info
                        db['page_buffer']=ebook.page_buffer
                        db['page_starts'] = ebook.page_starts 
        
                    return 'book_menu'
                if key is 'power':
                    with shelve.open(self.settings['selected_book']['path']+'_reader_data') as db:
                        db['view_page']=ebook.view_page    
                        db['location_info']=ebook.location_info
                        db['page_buffer']=ebook.page_buffer
                        db['page_starts'] = ebook.page_starts             
                    return 'quit'

                if key is 'right':
                    self.input_handler.thread_ble = threading.Thread(target=self.input_handler.connect_ble, args=())
                    self.input_handler.thread_ble.start()
                    #self.input_handler.connect_ble()
            if changed:
                print("button pressed")

                if direction == -1:
                    new_screen = ebook.previous_page()
                
                if direction == 1:
                    new_screen = ebook.next_page()

                if new_screen is not None:
                    screen = new_screen
                draw = ImageDraw.Draw(screen)
                print("getting ble state")
                state = self.input_handler.state
                print("got ble state")
                if state == 'conn':
                    draw.ellipse((1072-35-10, 1448-25-10,1072-20, 1448-10), fill = 0, outline =0)
                else:
                    draw.ellipse((1072-35-10, 1448-25-10,1072-20, 1448-10), fill = 255, outline =0)
                self.display.frame_buf.paste(ImageOps.invert(screen).rotate(180), (0,0))
                self.display.draw_full(constants.DisplayModes.GC16)
                changed = False
                print(state)
            sleep(0.1)






def display_list(item_list, settings):

    active_element = settings.get('active',None)
    if active_element is not None and active_element >= len(item_list):
        if len(item_list)==0:
            active_element = None
        else:
            active_element = 0
    image = Image.new('L', settings['canvas_shape'],255)
    print(image.size)
    draw = ImageDraw.Draw(image)
    font_normal = ImageFont.truetype("/usr/share/fonts/truetype/ttf-dejavu/DejaVuSans.ttf", settings['font_size'],layout_engine=ImageFont.LAYOUT_RAQM)
    font_selected= ImageFont.truetype("/usr/share/fonts/truetype/ttf-dejavu/DejaVuSans-Bold.ttf", settings['font_size'],layout_engine=ImageFont.LAYOUT_RAQM)
    margin = settings['margin']
    offset = settings['margin'] + settings['line_spacing']
    for i, line in enumerate(item_list):
        text=textwrap.wrap(line, width=settings.get('text_width',50))
        for t in text:
            if i == active_element:
                font = font_selected
                t = '> '+t
            else:
                font = font_normal
            draw.text((margin, offset), t, font=font, fill=0)
            offset += font.getsize(line)[1] + settings['line_spacing']
        offset += settings['list_spacing']
    return image.rotate(180, expand=True)





if __name__ == "__main__":

    m = master_program([])
    m.launch()



