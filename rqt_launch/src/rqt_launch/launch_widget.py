# Software License Agreement (BSD License)
#
# Copyright (c) 2012, Willow Garage, Inc.
# All rights reserved.
#
# Redistribution and use in source and binary forms, with or without
# modification, are permitted provided that the following conditions
# are met:
#
#  * Redistributions of source code must retain the above copyright
#    notice, this list of conditions and the following disclaimer.
#  * Redistributions in binary form must reproduce the above
#    copyright notice, this list of conditions and the following
#    disclaimer in the documentation and/or other materials provided
#    with the distribution.
#  * Neither the name of Willow Garage, Inc. nor the names of its
#    contributors may be used to endorse or promote products derived
#    from this software without specific prior written permission.
#
# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS
# "AS IS" AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT
# LIMITED TO, THE IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS
# FOR A PARTICULAR PURPOSE ARE DISCLAIMED. IN NO EVENT SHALL THE
# COPYRIGHT OWNER OR CONTRIBUTORS BE LIABLE FOR ANY DIRECT, INDIRECT,
# INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES (INCLUDING,
# BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES;
# LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER
# CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT
# LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN
# ANY WAY OUT OF THE USE OF THIS SOFTWARE, EVEN IF ADVISED OF THE
# POSSIBILITY OF SUCH DAMAGE.
#
# Author: Isaac Saito

import os
import sys

from python_qt_binding import loadUi
from python_qt_binding.QtCore import QSize
from python_qt_binding.QtGui import (QDialog, QGridLayout, QLabel, QLineEdit,
                                     QPushButton, QStyle, QToolButton, QWidget)
import roslaunch
from roslaunch.core import RLException
import rospkg
import rospy

from rqt_launch.node_proxy import NodeProxy
from rqt_launch.node_controller import NodeController
from rqt_launch.node_gui import NodeGui
from rqt_launch.name_surrogate import NamesSurrogate
from rqt_launch.status_indicator import StatusIndicator
from rqt_py_common.rqt_roscomm_util import RqtRoscommUtil


class LaunchWidget(QDialog):
    """
    #TODO: comment
    """

    def __init__(self, config, parent):
        """
        @type parent: LaunchMain
        @type config: ?
        """
        super(LaunchWidget, self).__init__()
        self._parent = parent
        self._config = config

        #TODO: should be configurable from gui
        self._port_roscore = 11311

        self.run_id = None
        rospy.loginfo(self._config.summary())
        # rospy.loginfo("MASTER", self._config.master.uri)  # Sheds error.
        #TODO: Replace 'print' with ROS-y method.
        print "MASTER", self._config.master.uri

        self._rospack = rospkg.RosPack()

        ui_file = os.path.join(self._rospack.get_path('rqt_launch'),
                               'resource', 'launch_widget.ui')
        loadUi(ui_file, self)

        #TODO: this layout is temporary. Need to be included in .ui.
        self._gridlayout_process = None

        self._pushbutton_start_stop_all.clicked.connect(self._parent.start_all)
        # Bind package selection with .launch file selection.
        self._combobox_pkg.currentIndexChanged[str].connect(
                                                 self._refresh_launchfiles)
        # Bind a launch file selection with launch GUI generation.
        self._combobox_launchfile_name.currentIndexChanged[str].connect(
                                                 self._load_launchfile_slot)
        self._refresh_packages()

    def _load_launchfile_slot(self, launchfile_name):

        # Not yet sure why, but everytime combobox.currentIndexChanged occurs,
        # this method gets called twice with launchfile_name=='' in 1st call.
        if launchfile_name == None or launchfile_name == '':
            return

        _config = None

        rospy.loginfo('_load_launchfile_slot launchfile_name={}'.format(
                                                launchfile_name))

        try:
            _config = self._create_launchconfig(launchfile_name,
                                                self._port_roscore)
        except IndexError as e:
            #TODO: Show error msg on GUI
            rospy.logerr('IndexError={} launchfile_name={}'.format(
                                                e.message, launchfile_name))
            return
        except RLException as e:
            #TODO: Show error msg on GUI
            rospy.logerr('RLException={} launchfile_name={}'.format(
                                                e.message, launchfile_name))
            return

        self._create_gui_for_launchfile(_config)

    def _create_launchconfig(self, launchfile_name,
                             port_roscore=11311,
                             folder_name_launchfile='launch'):
        """
        @raises IndexError:
        @raises RLException: raised by roslaunch.config.load_config_default.
        """

        #TODO: folder_name_launchfile foShould be able to specify arbitrarily.

        pkg_name = self._combobox_pkg.currentText()

        try:
            launchfile = os.path.join(self._rospack.get_path(pkg_name),
                                      folder_name_launchfile, launchfile_name)
        except IndexError as e:
            #TODO: Return exception to show error msg on GUI
            raise e

        try:
            launch_config = roslaunch.config.load_config_default([launchfile],
                                                                 port_roscore)
        except RLException as e:
            raise e

        return launch_config

    def _create_gui_for_launchfile(self, config):
        """
        """
        self._config = config

        # Renew the layout of nodes
        #TODO this layout is temporary. Need to be included in .ui.
        self._vlayout.removeWidget(self._process_widget)
        _process_widget_previous = self._process_widget
        # QWidget.hide() was necessary in order NOT to show the previous
        # widgets. See http://goo.gl/9hjFz
        _process_widget_previous.hide()
        #del self._process_widget
        self._process_widget = QWidget(self)
        self._vlayout.insertWidget(1, self._process_widget)
        self._gridlayout_process = QGridLayout()

        # Creates the process grid
        self._node_controllers = []
        # Loop per node
        for i, node_config in enumerate(self._config.nodes):
            _proxy = NodeProxy(self.run_id, self._config.master.uri,
                              node_config)

            # TODO: consider using QIcon.fromTheme()
            status = StatusIndicator()
            start_button = QPushButton(self.style().standardIcon(
                                                      QStyle.SP_MediaPlay), "")
            start_button.setIconSize(QSize(16, 16))
            stop_button = QPushButton(self.style().standardIcon(
                                                      QStyle.SP_MediaStop), "")
            stop_button.setIconSize(QSize(16, 16))
            respawn_toggle = QToolButton()
            respawn_toggle.setIcon(self.style().standardIcon(
                                                      QStyle.SP_BrowserReload))
            respawn_toggle.setIconSize(QSize(16, 16))
            respawn_toggle.setCheckable(True)
            respawn_toggle.setChecked(_proxy.config.respawn)
            spawn_count_label = QLabel("(0)")
            launch_prefix_edit = QLineEdit(_proxy.config.launch_prefix)

            gui = NodeGui(status, respawn_toggle, spawn_count_label,
                          launch_prefix_edit)

            node_controller = NodeController(_proxy, gui)
            self._node_controllers.append(node_controller)

            # TODO: These need to be commented in in order to function as
            # originally intended.
            start_button.clicked.connect(node_controller.start)
            stop_button.clicked.connect(node_controller.stop)

            rospy.loginfo('loop #%d _proxy.config.namespace=%s ' +
                          '_proxy.config.name=%s',
                          i, _proxy.config.namespace, _proxy.config.name)
            resolved_node_name = NamesSurrogate.ns_join(
                                   _proxy.config.namespace, _proxy.config.name)

            j = 0
            self._gridlayout_process.addWidget(status, i, j)
            self._gridlayout_process.setColumnMinimumWidth(j, 20)
            j += 1
            self._gridlayout_process.addWidget(QLabel(resolved_node_name),
                                               i, j)
            j += 1
            self._gridlayout_process.addWidget(spawn_count_label, i, j)
            self._gridlayout_process.setColumnMinimumWidth(j, 30)
            j += 1
            self._gridlayout_process.setColumnMinimumWidth(j, 30)
            j += 1  # Spacer
            self._gridlayout_process.addWidget(start_button, i, j)
            j += 1
            self._gridlayout_process.addWidget(stop_button, i, j)
            j += 1
            self._gridlayout_process.addWidget(respawn_toggle, i, j)
            j += 1
            self._gridlayout_process.setColumnMinimumWidth(j, 20)
            j += 1  # Spacer
            self._gridlayout_process.addWidget(QLabel(_proxy.config.package),
                                               i, j)
            j += 1
            self._gridlayout_process.addWidget(QLabel(_proxy.config.type),
                                               i, j)
            j += 1
            self._gridlayout_process.addWidget(launch_prefix_edit, i, j)
            j += 1

        self._parent.set_node_controllers(self._node_controllers)
        # process_scroll.setMinimumWidth(self._gridlayout_process.sizeHint().width())
        # Doesn't work properly.  Too small

        self._process_widget.setLayout(self._gridlayout_process)

        # Creates the log display area
#        self.log_text = QPlainTextEdit()
#
#        # Sets up the overall layout
#        process_log_splitter = QSplitter()
#        process_log_splitter.setOrientation(Qt.Vertical)
#        process_log_splitter.addWidget(self.log_text)
#        main_layout = QVBoxLayout()
#        # main_layout.addWidget(process_scroll, stretch=10)
#        # main_layout.addWidget(self.log_text, stretch=30)
#        main_layout.addWidget(process_log_splitter)
#        self.setLayout(main_layout)

    def _refresh_packages(self):
        """
        Inspired by rqt_msg.MessageWidget._refresh_packages
        """
        packages = sorted([pkg_tuple[0]
                           for pkg_tuple
                           in RqtRoscommUtil.iterate_packages('launch')])
        self._package_list = packages
        rospy.loginfo('pkgs={}'.format(self._package_list))
        self._combobox_pkg.clear()
        self._combobox_pkg.addItems(self._package_list)
        self._combobox_pkg.setCurrentIndex(0)

    def _refresh_launchfiles(self, package=None):
        """
        Inspired by rqt_msg.MessageWidget._refresh_msgs
        """
        if package is None or len(package) == 0:
            return
        self._launchfile_instances = []  # Launch[]
        #TODO: RqtRoscommUtil.list_files's 2nd arg 'subdir' should NOT be
        # hardcoded later.
        _launch_instance_list = RqtRoscommUtil.list_files(package,
                                                         'launch')

        rospy.logdebug('_refresh_launches package={} instance_list={}'.format(
                                                       package,
                                                       _launch_instance_list))

        self._launchfile_instances = [x.split('/')[1]
                                      for x in _launch_instance_list]

        self._combobox_launchfile_name.clear()
        self._combobox_launchfile_name.addItems(self._launchfile_instances)

    def shutdown(self):
        # TODO: Needs implemented. Trigger dynamic_reconfigure to unlatch
        #            subscriber.
        pass

    def save_settings(self, plugin_settings, instance_settings):
        # instance_settings.set_value('splitter', self._splitter.saveState())
        pass

    def restore_settings(self, plugin_settings, instance_settings):
#        if instance_settings.contains('splitter'):
#            self._splitter.restoreState(instance_settings.value('splitter'))
#        else:
#            self._splitter.setSizes([100, 100, 200])
        pass


if __name__ == '__main__':
    # main should be used only for debug purpose.
    # This launches this QWidget as a standalone rqt gui.
    from rqt_gui.main import Main

    main = Main()
    sys.exit(main.main(sys.argv, standalone='rqt_launch'))