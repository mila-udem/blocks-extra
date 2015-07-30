import logging
import signal
import time
from subprocess import Popen, PIPE

try:
    from bokeh.plotting import (curdoc, cursession, figure, output_server,
                                push, show)
    from bokeh.util.platform import is_notebook
    BOKEH_AVAILABLE = True
except ImportError:
    BOKEH_AVAILABLE = False


from blocks.config import config
from blocks.extensions import SimpleExtension

logger = logging.getLogger(__name__)


class Plot(SimpleExtension):
    """Live plotting of monitoring channels.

    In most cases it is preferable to start the Bokeh plotting server
    manually, so that your plots are stored permanently.

    Alternatively, you can set the ``start_server`` argument of this
    extension to ``True``, to automatically start a server when training
    starts. However, in that case your plots will be deleted when you shut
    down the plotting server!

    .. warning::

       When starting the server automatically using the ``start_server``
       argument, the extension won't attempt to shut down the server at the
       end of training (to make sure that you do not lose your plots the
       moment training completes). You have to shut it down manually (the
       PID will be shown in the logs). If you don't do this, this extension
       will crash when you try and train another model with
       ``start_server`` set to ``True``, because it can't run two servers
       at the same time.

    Parameters
    ----------
    document : str
        The name of the Bokeh document. Use a different name for each
        experiment if you are storing your plots.
    channels : list of lists of strings
        The names of the monitor channels that you want to plot. The
        channels in a single sublist will be plotted together in a single
        figure, so use e.g. ``[['test_cost', 'train_cost'],
        ['weight_norms']]`` to plot a single figure with the training and
        test cost, and a second figure for the weight norms.
    open_browser : bool, optional
        Whether to try and open the plotting server in a browser window.
        Defaults to ``True``. Should probably be set to ``False`` when
        running experiments non-locally (e.g. on a cluster or through SSH).
    start_server : bool, optional
        Whether to try and start the Bokeh plotting server. Defaults to
        ``False``. The server started is not persistent i.e. after shutting
        it down you will lose your plots. If you want to store your plots,
        start the server manually using the ``bokeh-server`` command. Also
        see the warning above.
    server_url : str, optional
        Url of the bokeh-server. Ex: when starting the bokeh-server with
        ``bokeh-server --ip 0.0.0.0`` at ``alice``, server_url should be
        ``http://alice:5006``. When not specified the default configured
        by ``bokeh_server`` in ``.blocksrc`` will be used. Defaults to
        ``http://localhost:5006/``.

    """
    # Tableau 10 colors
    colors = ['#1f77b4', '#ff7f0e', '#2ca02c', '#d62728', '#9467bd',
              '#8c564b', '#e377c2', '#7f7f7f', '#bcbd22', '#17becf']

    def __init__(self, document, channels, open_browser=False,
                 start_server=False, server_url=None, **kwargs):
        if not BOKEH_AVAILABLE:
            raise ImportError

        if server_url is None:
            server_url = config.bokeh_server

        self.plots = {}
        self.start_server = start_server
        self.document = document
        self.server_url = server_url

        self.in_notebook = False
        if cursession() is not None:
            self.in_notebook = is_notebook()

        self._startserver()

        # Create figures for each group of channels
        self.p = []
        self.p_indices = {}
        for i, channel_set in enumerate(channels):
            fig = figure(title='{} #{}'.format(document, i + 1),
                         x_axis_label='iterations',
                         y_axis_label='value')

            for j, channel in enumerate(channel_set):
                self.p_indices[channel] = i
                fig.line([], [], legend=channel, name=channel,
                         line_color=self.colors[j % len(self.colors)])

            self.p.append(fig)
            if self.in_notebook or open_browser:
                show(fig)

            for j, channel in enumerate(channel_set):
                    renderer = fig.select(dict(name=channel))
                    self.plots[channel] = renderer[0].data_source

        # if open_browser:
        #     show()

        kwargs.setdefault('after_epoch', True)
        kwargs.setdefault("before_first_epoch", True)
        super(Plot, self).__init__(**kwargs)

    def do(self, which_callback, *args):
        # print("plot:do")
        log = self.main_loop.log
        iteration = log.status['iterations_done']

        for key, value in log.current_row.items():
            if key in self.p_indices:
                if key not in self.plots:
                    print("Missing key '%s'" % (key))
                else:
                    self.plots[key].data['x'].append(iteration)
                    self.plots[key].data['y'].append(value)

                    if cursession() is not None:
                        cursession().store_objects(self.plots[key])
                    else:
                        print("plot:cursession() is None")
                    # print("plot:data.x=%s" % (self.plots[key].data['x']))

        push()

    def _startserver(self):
        if self.start_server:
            def preexec_fn():
                """Prevents the server from dying on training interrupt."""
                signal.signal(signal.SIGINT, signal.SIG_IGN)
            # Only memory works with subprocess, need to wait for it to start
            logger.info('Starting plotting server on localhost:5006')
            self.sub = Popen('bokeh-server --ip 0.0.0.0 '
                             '--backend memory'.split(),
                             stdout=PIPE, stderr=PIPE, preexec_fn=preexec_fn)
            time.sleep(2)
            logger.info('Plotting server PID: {}'.format(self.sub.pid))
        else:
            self.sub = None

        if not self.in_notebook:
            output_server(self.document, url=self.server_url)

    def __getstate__(self):
        state = self.__dict__.copy()
        state['sub'] = None
        return state

    def __setstate__(self, state):
        self.__dict__.update(state)
        self._startserver()
        curdoc().add(*self.p)
