# -*- coding: utf-8 -*-
# Copyright: Kyle Hwang <feathered.hwang@hotmail.com>
# License: GNU GPL, version 3 or later; http://www.gnu.org/copyleft/gpl.html


import logging
import os
import sys
import re

from anki.notes import NoteId

# import markdown2 from the local libray, cause Anki doesn't include this module
try:
    from .Lib import markdown2
    # TODO markdown2 parser doesn't support latex
    # todo markdown2 parser doesn't support :star: (emoji)
except ImportError as import_error:
    logging.warning(f'"markdown2" module not found, exit: {import_error}')
    sys.exit()

from bs4 import BeautifulSoup, Tag, NavigableString, Comment

from anki.decks import DeckId
from anki.models import ModelManager, NotetypeDict, TemplateDict, MODEL_CLOZE
from anki.notes import Note
from aqt import mw

# legacy types
HeadingRoot = dict[str, str]


# mm: ModelManager = mw.col.models  # AttributeError: 'NoneType' object has no attribute 'models'
#   mw is None before profile-loaded


class MdJoint:
    """
    MdJoint is a model with join() function which import notes from markdown files.
    # TODO Archive Anki Deck
    """

    DEFAULT_NAME: str = 'Basic'
    FILE_SUFFIX: str = 'basic'

    content: str
    soup: BeautifulSoup
    new_notes_count: int

    HEADINGS: list[str] = [f'h{n}' for n in range(1, 7)]

    def __init__(self, model_name: str = DEFAULT_NAME):
        # Using model manager is the only way to add new model
        # verify if model exists
        m = mw.col.models.byName(model_name)
        if m:
            # TODO How to update the model? Using version to keep user's custom changes
            logging.info(f'Initialize model: "{model_name}" model already exists, skip building.')
        else:
            # build model if not exists
            self.build(model_name)

        self.new_notes_count = 0

    def build(self, model_name: str = DEFAULT_NAME):
        """
        Build up the model but not add to Anki yet
        """
        mm: ModelManager = mw.col.models

        logging.info(f'Initialize model: Building Model "{model_name}" started.')
        m: NotetypeDict = mm.new(model_name)
        # TODO build "basic" model
        # Add the Model (NoteTypeDict) to Anki
        mm.add_dict(notetype=m)
        logging.info(f'Initialize model: Building Model "{model_name}" finished.')

    def join(self, file: str, deck_name: str):
        """
        Parse the file content, map them on the model,
        then add/join them to collection.
        :param file: filepath of the kb md-format file
        :param deck_name: deck name where to import notes to
        """
        pass

    def verify(self, file: str) -> bool:
        """
        check if the file appropriate for the model
        :param file: filepath
        :return: appropriate or not
        """
        # TODO file analyse - if suitable for this model/joint
        pass

    @staticmethod
    def read(file: str) -> str:
        """
        Open the file and read the file content.
        :param file: The path of the file to read from.
        :return: The content of the file.
        """
        try:
            # Attempt to open the file
            with open(file, 'r', encoding='utf-8') as f:
                # Read the entire content of the file
                file_content = f.read()
                logging.debug(f'File read done: "{file}"')
                return file_content
        except FileNotFoundError:
            logging.error(f'File-read error: File not found: "{file}"')
        except IOError as e:
            logging.error(f'File-read error: "{file}" {e}')
        return ''

    @staticmethod
    def write(file: str, content: str):
        """
        Write content to a file.
        :param content: The content to write to the file.
        :param file: The path of the file to write to.
        """
        try:
            with open(file, 'w', encoding='utf-8') as f:
                f.write(content)
            logging.debug(f'File-write done: "{file}"')
        except Exception as e:
            logging.error(f'File-write error: "{file}" {e}')

    def make_soup(self, file: str):
        self.content = self.read(file)
        html = markdown2.markdown(self.content)
        self.soup = BeautifulSoup(html, 'html.parser')

    def comment_noteid(self, heading: Tag, note_id: NoteId):
        """
        add comment of NoteId for new notes
        :param heading:
        :param note_id:
        """
        self.content = re.sub(
            r'(\n#+\s*{}\s*\n\n)'.format(heading.text),
            r'\1' + f'<!-- NoteId: {note_id} -->\n\n',
            self.content)
        # there must be two '\n' at the end of the pattern,
        #  or the comment will be parsed as part of next element in markdown2
        logging.debug(f'NoteId commented after heading "{heading.text}".')

    def get_commented_noteid(self, heading: Tag) -> NoteId:
        """
        Get the noteid from comment right after the heading tag
        :param heading:
        :return:
        """
        self.check_heading(heading)

        comm = heading.next_sibling
        while comm and isinstance(comm, NavigableString):
            if isinstance(comm, Comment):
                break
            else:
                comm = comm.next_sibling
        else:
            return NoteId(0)
        m = re.fullmatch(
            r'\s*NoteId:\s*(?P<note_id>[0-9]{13})\s*',
            comm,
            flags=re.IGNORECASE
        )
        note_id = NoteId(m.group('note_id')) if m else None
        return note_id

    def get_heading_soup(self, heading: Tag, subheading: bool = False) -> BeautifulSoup:
        """
        find the content of heading
        :param heading:
        :param subheading:
        :return:
        """
        self.check_heading(heading)

        text: str = ''
        sibling = heading.find_next_sibling()  # Attention: .next_sibling might return NavigableString
        # todo include subheading
        # if subheading:
        while sibling and sibling.name not in self.HEADINGS and sibling.name != 'hr':
            text += str(sibling)
            sibling = sibling.find_next_sibling()
        return BeautifulSoup(text, 'html.parser')

    def get_heading_root(self, heading: Tag) -> HeadingRoot:
        self.check_heading(heading)

        index = self.HEADINGS.index(heading.name)
        heading_root: HeadingRoot = {}
        # start from h1, h2...
        for n in range(index):
            heading_root[self.HEADINGS[n]] = heading.find_previous_sibling(self.HEADINGS[n]).text
        # and end with current heading
        heading_root[heading.name] = heading.text

        return heading_root

    def check_heading(self, heading: Tag):
        # Check if the tag is part of a BeautifulSoup instance
        if heading.parent is not self.soup:
            raise ValueError("Heading tag comes from another parse tree.")


class ClozeJoint(MdJoint):
    DEFAULT_NAME: str = 'Cloze (traceable)'
    FILE_SUFFIX: str = 'traceable'

    NORMAL_FIELDS: list[str] = [
        'root',  # used to traceback to sections in the book
        'Text',
        'Extra',
    ]
    TRACEBACK_MAP: HeadingRoot = {
        'h1': 'Chapter',
        'h2': 'Section',
        'h3': 'Subsection',
    }

    def __init__(self, model_name=DEFAULT_NAME):
        self.model_name = model_name
        super().__init__(model_name=model_name)

    def build(self, model_name: str = DEFAULT_NAME):

        mm: ModelManager = mw.col.models
        logging.info(f'Initialize model: Building Model "{model_name}" started.')

        m: NotetypeDict = mm.new(model_name)
        # as cloze type
        m["type"] = MODEL_CLOZE

        # Add fields
        for fld_name in self.NORMAL_FIELDS:
            fld = mm.newField(fld_name)
            fld['size'] = 15
            fld['plainText'] = True
            mm.addField(m, fld)
        mm.set_sort_index(m, self.NORMAL_FIELDS.index('root'))

        for fld_name in self.TRACEBACK_MAP.values():
            fld = mm.newField(fld_name)
            fld['plainText'] = True
            fld['collapsed'] = True
            fld['excludeFromSearch'] = True
            mm.addField(m, fld)

        # Set the working directory to the path of current Python script
        #   used to find template files by absolute path
        os.chdir(os.path.dirname(os.path.abspath(__file__)))
        logging.debug(f'Current working directory is: {os.getcwd()}')

        # Add card template
        t: TemplateDict = mm.newTemplate()
        t['qfmt'] = self.read('templates/cloze_front.html')
        t['afmt'] = self.read('templates/cloze_back.html')
        mm.addTemplate(m, t)

        # Add css
        m['css'] = self.read('templates/css.css')

        # Add the Model (NoteTypeDict) to Anki
        mm.add_dict(notetype=m)

        logging.info(f'Initialize model: Building Model "{model_name}" finished.')

    def join(self, file: str, deck_name: str):
        """
        Parse the file content, map them on the model,
        then add/join them to collection.
        :param file: filepath of the kb md-format file
        :param deck_name: deck name where to import notes to
        """
        self.make_soup(file)

        # Traverse every heading and create note for it
        for heading in self.soup.find_all(self.TRACEBACK_MAP.keys()):

            # get heading_root
            heading_root: HeadingRoot = self.get_heading_root(heading)
            root_str = '.'.join(heading_root.values())

            # Check if heading has been imported (commented with note_id)
            noteid = self.get_commented_noteid(heading)
            if noteid:
                logging.debug(f'Importing MD - note already imported: "{root_str}"')
                continue

            # check if heading has cloze-deletion
            cloze_text = self.get_cloze_text(heading)
            if not cloze_text:
                logging.debug(f'Importing MD - cloze-deletion not found under heading, continue: "{heading.name}"')
                continue

            # Create a note
            logging.debug(f'Importing MD - New note: <{heading.name}> {heading.text}')
            note = Note(mw.col, mw.col.models.byName(self.model_name))
            note['Text'] = cloze_text
            note['root'] = root_str

            for key, value in heading_root.items():
                note[self.TRACEBACK_MAP[key]] = value
            if '⭐' in note['root']:  # re.search also works, but re.match doesn't
                note.tags.append('marked')
            # todo what about user-defined tags

            # find deck or create if not exist
            deck_id: DeckId = mw.col.decks.id(deck_name)

            # add note to deck, and the note object will get assigned with id
            mw.col.add_note(note, deck_id)
            self.comment_noteid(heading, note.id)
            self.new_notes_count += 1
            logging.info(f'Importing MD: Note added, note.id: {note.id}')

        # Finally, refresh the source file with comment
        self.write(file, self.content)

    def get_cloze_text(self, heading: Tag) -> str:
        heading_soup: BeautifulSoup = self.get_heading_soup(heading)
        cloze_text: str = ''.join(str(tag) for tag in heading_soup.find_all(['p', 'ol', 'ul']))
        # Skip if empty
        if not cloze_text:
            return ''

        cloze_soup: BeautifulSoup = BeautifulSoup(cloze_text, 'html.parser')

        # find all cloze-deletion
        cloze_tags: list[Tag] = []
        cloze_tags += cloze_soup.find_all('strong')
        cloze_tags += cloze_soup.select('li > p') if not cloze_tags else []
        cloze_tags += cloze_soup.select('li') if not cloze_tags else []
        # todo pure list didn't have strong effect

        # Skip notes that doesn't contain cloze-deletion
        if not cloze_tags:
            return ''

        # cloze deletion - replace all cloze
        cloze_count = 0
        for cloze_tag in cloze_tags:
            cloze_count += 1
            p = '({})'.format(cloze_tag.string)
            r = r'{{c%d::\1}}' % cloze_count
            cloze_text = re.sub(p, r, cloze_text)
            # logging.debug('Text field after cloze-deletion: ' + note['Text'])

        return cloze_text


class OnesideJoint(MdJoint):
    pass
