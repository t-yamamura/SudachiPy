from enum import Enum
from enum import auto

from . import lattice
from . import latticenode
from . import morphemelist
from . import utf8inputtextbuilder


class Tokenizer:
    class SplitMode(Enum):
        A = auto()
        B = auto()
        C = auto()

    def __init__(self, grammar, lexicon, input_text_plugins, oov_provider_plugins, path_rewrite_plugins):
        self.grammar = grammar
        self.lexicon = lexicon
        self.input_text_plugins = input_text_plugins
        self.oov_provider_plugins = oov_provider_plugins
        self.path_rewrite_plugins = path_rewrite_plugins
        # self.dump_output = None
        self.lattice = lattice.Lattice(grammar)

    def tokenize(self, mode, text):
        if len(text) is 0:
            return []

        builder = utf8inputtextbuilder.UTF8InputTextBuilder(text, self.grammar)
        for plugin in self.input_text_plugins:
            plugin.rewrite(builder)
        input_ = builder.build()
        bytes_ = input_.get_byte_text()

        self.lattice.resize(len(bytes_))
        for i in range(len(bytes_)):
            if not input_.is_char_alignment(i) or not self.lattice.has_previous_node(i):
                continue
            iterator = self.lexicon.lookup(bytes_, i)
            has_words = True if iterator else False
            for word_id, end in iterator:
                n = latticenode.LatticeNode(self.lexicon,
                                                    self.lexicon.get_left_id(word_id),
                                                    self.lexicon.get_right_id(word_id),
                                                    self.lexicon.get_cost(word_id),
                                                    word_id)
                self.lattice.insert(i, end, n)

            # OOV
            for plugin in self.oov_provider_plugins:
                for node in plugin.get_oov(input_, i, has_words):
                    has_words = True
                    self.lattice.insert(node.get_begin(), node.get_end(), node)
            if not has_words:
                raise AttributeError("there is no morpheme at " + str(i))

        # dump_output

        path = self.lattice.get_best_path()
        self.lattice.clear()

        path.pop()  # remove EOS
        # dump_output

        for plugin in self.path_rewrite_plugins:
            plugin.rewrite(input_, path, self.lattice)

        if mode is not self.SplitMode.C:
            new_path = []
            for node in path:
                if mode is self.SplitMode.A:
                    wids = node.get_word_info().get_Aunit_split()
                else:  # self.SplitMode.B
                    wids = node.get_word_info().get_Bunit_split()
                if len(wids) is 0 or len(wids) is 1:
                    new_path.append(node)
                else:
                    offset = node.get_begin()
                    for wid in wids:
                        n = latticenode.LatticeNode(self.lexicon, 0, 0, 0, wid)
                        n.begin = offset
                        offset += n.get_word_info().get_length()
                        n.end = offset
                        new_path.append(n)
            path = new_path

        # dump_output

        ml = morphemelist.MorphemeList(input_, self.grammar, self.lexicon, path)
        return ml
