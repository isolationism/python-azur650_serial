#!/usr/bin/python

"""
A library for controlling a Cambridge Audio Azur 650R Amplifier over RS232
serial cable.

Requirements:
-------------

* A Cambridge Audio Azur 650R integrated amplifier
* A computer (to act as the serial controller) with a free serial port
* A null-modem cable with DB9F for connecting to the amplifier, and whatever
  connector is required on the computer side (also most commonly DB9f, unless
  you're using an embedded device like a plug computer). If you're making
  your own cable, make sure to cross pins 2 and 3.
* Python 2.6 or higher (may work with older versions; untested)
* Pyserial (python-pyserial in debian distributions) for serial communication

TODO: Instantiation instructions
"""

# Python modules
from time import sleep
from sys import exit

# Third-party modules
import serial


class CommandGroupError(KeyError):
    """
    Command Group Unknown
    """
    pass

class CommandNumberError(KeyError):
    """
    Command Number in Group Unknown
    """
    pass

class CommandDataError(ValueError):
    """
    Command Data Error
    """
    pass


class Azur650R(object):
    """
    Class for controlling a Cambridge Audio Azur 650R model amplifier.
    """

    input_names = {
        '00': 'Tuner',
        '01': 'BD/DVD',
        '02': 'Video 1',
        '03': 'Video 2',
        '04': 'Video 3',
        '05': 'Rec 1',
        '06': 'Aux',
        '07': 'CD',
        '08': 'Rec 2',
        '09': 'Tuner', # TODO: Confusing, why does this differ from set?
        '10': '7.1 Direct In',
    }

    audio_input_source = {
        '0': 'analogue',
        '1': 'digital',
        '2': 'HDMI',
    }

    video_input_source = {
        '0': 'S-video',
        '1': 'Component',
        '2': 'Composite',
        '3': 'HDMI',
    }

    stereo_audio_modes = {
        '00': 'Stereo',
        '01': 'Stereo + Subwoofer',
    }

    def __init__(self, serial_port='/dev/ttyS0'):
        """
        Creates a new Azur650R communication instance on the specified
        serial_port. You can either pass a string as a reference to the
        device node (e.g. '/dev/ttyS1' for the second serial port) or an
        integer (e.g. 1).

        Since the constructor opens the serial port, you should remember to
        call the close() method when you are done to release the port.

        N.B. that this class does a relatively 'complete' job of retaining
        state, meaning it may be useful to populate its values, then store
        (e.g. via pickle) somewhere between sessions so you have a complete
        state in memory instead of starting from scratch with each instance.
        Although some values may be modified externally (such as input
        section, volume, etc.) these are adjusted often and will be
        resynchronized frequently with updated information.
        """
        # Creates an (active) serial connection.
        self.__conn = serial.Serial(port=serial_port, baudrate=9600,
                                    bytesize=8, parity='N', stopbits=1,
                                    timeout=0.08)

        # Group 6: Amplifier commands
        self.__power_state = None
        self.__volume = None
        self.__bass = None
        self.__treble = None
        self.__subwoofer = None
        self.__lfe_trim = None
        self.__mute_state = None
        self.__dynamic_range = None
        self.__osd_on = None
        self.__lip_sync = None

        # Group 7: Source commands
        self.__active_input = None
        self.__audio_source_for_input = {
            '01': None,
            '02': None,
            '03': None,
            '04': None,
            '05': None,
            '06': None,
            '07': None,
            '08': None,
            '09': None,
        }
        self.__video_source_for_input = {
            '01': None,
            '02': None,
            '03': None,
            '04': None,
            '05': None,
            '06': None,
            '07': None,
            '08': None,
            '09': None,
        }

        # Group 8: Tuner commands
        # TODO

        # Group 9: Audio processing commands
        self.__stereo_audio_mode = None
        self.__signal_processing_mode = None
        self.__signal_codec = None

        # Group 10: Version commands
        self.__main_software_version = None
        self.__protocol_version = None

    def _cmd(self, command_group, command_number, command_data=None):
        """
        Send a low-level command to the amplifier; returns the low-level
        response without any processing applied. Not recommended for public
        use if you want to preserve state etc.

        Request commands are accepted as whatever you want, but will be
        converted to a string before transmission. Responses are always
        returned as strings because some commands use leading zeros and
        some don't, and some commands return strings by default.
        """
        # Compose the command sequence
        command = '#%s,%s' % (command_group, command_number)
        if command_data: command = "%s,%s" % (command, command_data)

        # Write the command and flush the buffer
        self.__conn.write("%s\r" % command)
        self.__conn.flush()

        # Retrieve the command response.
        response = self.__conn.read(50)

        # How many unique replies are present in the response?
        responses = set( response.strip('\r').split('\r') )
        for response in responses:

            # Parse the response into a tuple
            response = tuple(response[1:].split(','))

            # If the response command group is 11, raise an appropriate exception
            if response[0] == '11':
                if response[1] == '01':
                    raise CommandGroupError("Unknown command group '%s'" % \
                                            command_group)
                elif response[1] == '02':
                    raise CommandNumberError("Unknown command number '%s'" % \
                                             command_number)
                elif response[1] == '03':
                    raise CommandDataError("Invalid command data '%s'" % \
                                           command_data)
                else:
                    raise ValueError("Invalid command '%s' [unknown error]" % \
                                     command)

            # Process the response code.
            self._parse_response(response)

        # No exceptions encountered; return a human-readable string
        return response

    def _parse_response(self, response):
        """
        Parses the response from the amplifier, modifying internal state
        accordingly.

        Yes, this is a very long method but it is easier to read than some
        strange mapping format.
        """
        # Amplifier commands
        if response[0] == '6':

            # Power state
            if response[1] == '01':
                if response[2] == '0': self.__power_state = False
                elif response[2] == '1': self.__power_state = True

            # Volume
            if response[1] in ['02', '03']: self.__volume = int(response[2])

            # Bass
            if response[1] in ['04', '05']: self.__bass = int(response[2])

            # Treble
            if response[1] in ['06', '07']: self.__treble = int(response[2])

            # Subwoofer (on/off)
            if response[1] == '08': self.__subwoofer = True
            elif response[1] == '09': self.__subwoofer = False

            # LFE trim; values are from 0 to -10dB.
            if response[1] == '10': self.__lfe_trim = -1 * int(response[2])

            # Mute
            if response[1] == '11':
                if response[2] == '1': self.__mute_state = True
                elif response[2] == '0': self.__mute_state = False

            # Dynamic Range (store as float)
            if response[1] == '12':
                if response[2] == '0': self.__dynamic_range = 0.0
                elif response[2] == '1': self.__dynamic_range = 0.25
                elif response[2] == '2': self.__dynamic_range = 0.5
                elif response[2] == '3': self.__dynamic_range = 0.75
                elif response[2] == '4': self.__dynamic_range = 1.0

            # OSD
            if response[1] == '13': self.__osd_on = True
            if response[1] == '14': self.__osd_on = False

            # Lip sync
            if response[1] in ['20', '21']: self.__lip_sync = int(response[2])

        # Source commands
        if response[0] == '7':

            # Input selection
            if response[1] == '01': self.__active_input = response[2]

            # Audio source
            if response[1] == '04' and self.__active_input is not None:
                self.__audio_source_for_input[self.__active_input] = \
                                                                response[2]

            # Video source
            if response[1] == '05' and self.__active_input is not None:
                self.__video_source_for_input[self.__active_input] = \
                                                                response[2]

        # Tuner commands
        # TODO

        # Audio processing commands
        if response[0] == '9':

            # Stereo mode
            if response[1] == '01': self.__stereo_audio_mode = response[2]

            # Digital processing mode
            if response[1] in ['02', '04']:
                self.__signal_processing_mode = response[2]

            # Signal CODEC
            if response[1] in ['03', '05']:
                self.__signal_codec = response[2]


        # Version commands
        if response[0] == '10':

            # Main software version
            if response[1] == '01': self.__main_software_version = response[2]

            # Protocol version
            if response[1] == '02': self.__protocol_version = response[2]

    def _set_value(self, set_level, set_pointer, increment_callback,
                   decrement_callback, min, max):
        """
        A private method for setting an internal value to an explicit value
        (as opposed to merely raising or lowering the value).

        This
        """
        # Sanity checks
        if not isinstance(set_level, (int, long)):
            try:
                set_level = int(set_level)
            except ValueError:
                raise TypeError("set_level must be a base-10 integer, "
                                "or an integer-like string")
        if set_level > max or set_level < min: raise ValueError("set_level " \
                        "must be a value between '%s' and '%s'" % (min, max))

        # If no current value known, change it experimentally to find out.
        try:
            if set_pointer is None: set_pointer = decrement_callback()
        except CommandDataError:
            set_pointer = increment_callback()

        # Does the value need to go up or down?
        if set_level < set_pointer:
            action = decrement_callback
            ascending = False
        elif set_level > set_pointer:
            action = increment_callback
            ascending = True
        elif set_level == set_pointer: return # Current value is OK!

        # Change the volume until it is correct.
        while set_pointer != set_level:
            # Because not all levels increment in steps of 1 unit, make sure
            # we haven't overshot before executing.
            if (ascending and set_pointer < set_level) or \
               (not ascending and set_pointer > set_level):
                set_pointer = int(action())
            else:
                break


        return set_level

    def disconnect(self):
        """
        Closes the connection to the amplifier by closing the serial port.
        No further communication will be possible until connect() is called.
        """
        self.__conn.close()

    def connect(self):
        """
        (Re-)opens the connection to the amplifier.
        """
        self.__conn.open()

    # Group 1: Amplifier commands --------------------------------------------

    def power_on(self):
        """
        Turn the amplifier from 'standby' to 'on'. The amplifier replies with
        the currently-selected input, and a response that the power has been
        enabled.
        """
        return self._cmd('1', '01', '1')

    def power_off(self):
        """
        Turns the amplifier to 'standby' mode.
        """
        return self._cmd('1', '01', '0')

    def volume_up(self):
        """
        Increases the volume, presumably by one db
        """
        return self._cmd('1', '02')[2]

    def volume_down(self):
        """
        Decreases the volume, presumably by one db
        """
        return self._cmd('1', '03')[2]

    def set_volume(self, level):
        """
        Increases (or decreases) the volume to an explicit sound pressure as
        measured in "-db", the same units as the amplifer. -90db is equivalent
        to muted, and 0db will destroy your speakers.

        Unlike other methods, it returns only the volume you define.
        """
        return self._set_value(level, self.__volume, self.volume_up,
                               self.volume_down, -90, 0)

    def bass_up(self):
        """
        Increases the bass level.
        """
        return int(self._cmd('1', '04')[2])

    def bass_down(self):
        """
        Decreases the bass level.
        """
        return int(self._cmd('1', '05')[2])

    def set_bass(self, level):
        """
        Sets the bass to the desired level; Acceptable values are from
        between -10 and 10 (db).
        """
        return self._set_value(level, self.__bass, self.bass_up,
                               self.bass_down, -10, 10)

    def treble_up(self):
        """
        Increases the treble level; returns the current treble level (as
        a string) in format "+ 4", " 0", or "- 4" up to an integer of 10
        in 2-value increments.
        """
        return int(self._cmd('1', '06')[2])

    def treble_down(self):
        """
        Decreases the treble level; returns the current treble level (as
        a string) in format "+ 4", " 0", or "- 4" up to an integer of 10
        in 2-value increments.
        """
        return int(self._cmd('1', '07')[2])

    def set_treble(self, level):
        """
        Like set_bass, but for treble response.
        """
        return self._set_value(level, self.__treble, self.treble_up,
                               self.treble_down, -10, 10)

    def sub_on(self):
        """
        Turns the subwoofer on; returns True
        """
        result = self._cmd('1', '08')
        return True

    def sub_off(self):
        """
        Turns the subwoofer off; returns False
        """
        result = self._cmd('1', '09')
        return False

    def set_lfe_trim(self, value):
        """
        Sets the LFE trim from between 0 and -10dB; value can be either
        positive or negative (but always "means" a negative value).

        Unlike most other values, there is no way to increment/decrement the
        trim; you just set it to whatever value you want directly.

        The value is returned as a negative integer.
        """
        if isinstance(value, (str, unicode)):
            value = int(value)
        value = str(abs(value))
        return 0 - int(self._cmd('1', '10', value)[2])

    def mute(self):
        """
        Mutes the audio output; returns True.
        """
        result = self._cmd('1', '11', '01')
        return True

    def unmute(self):
        """
        Unmutes the audio output; returns False.
        """
        result = self._cmd('1', '11', '00')
        return False

    def show_osd(self):
        """
        Show the on-screen-display; returns True
        """
        result = self._cmd('1', '13')
        return True

    def hide_osd(self):
        """
        Hide the on-screen display; returns False
        """
        result = self._cmd('1', '14')
        return False

    def osd_cursor_up(self):
        """
        Move the OSD cursor up
        """
        return self._cmd('1', '15')

    def osd_cursor_down(self):
        """
        Move the OSD cursor down
        """
        return self._cmd('1', '16')

    def osd_cursor_left(self):
        """
        Move the OSD cursor left
        """
        return self._cmd('1', '17')

    def osd_cursor_right(self):
        """
        Move the OSD cursor right
        """
        return self._cmd('1', '18')

    def osd_enter(self):
        """
        Selects the highlighted OSD option
        """
        return self._cmd('1', '19')

    def lip_sync_decrease(self):
        """
        Decrease the time delay for lip sync by one iteration
        """
        return int(self._cmd('1', '20')[2])

    def lip_sync_increase(self):
        """
        Increase the time delay for lip sync by one iteration
        """
        return int(self._cmd('1', '21')[2])

    # Group 2: Source Commands -----------------------------------------------

    def input_select(self, input_id):
        """
        Select the input directly using its unique ID
        """
        if input_id not in self.input_names.keys():
            raise KeyError("No input with ID '%s'" % input_id)
        return self._cmd('2', '01', input_id)

    def select_tuner_input(self):
        """
        Select Tuner input
        """
        return self.input_select('00')

    def select_bddvd_input(self):
        """
        Select BD/DVD input
        """
        return self.input_select('01')

    def select_video1_input(self):
        """
        Select Video 1 Input
        """
        return self.input_select('02')

    def select_video2_input(self):
        """
        Select Video 2 Input
        """
        return self.input_select('03')

    def select_video3_input(self):
        """
        Select Video 3 Input
        """
        return self.input_select('04')

    def select_rec1_input(self):
        """
        Select Rec 1 Input
        """
        return self.input_select('05')

    def select_aux_input(self):
        """
        Select Aux 1 Input
        """
        return self.input_select('06')

    def select_cd_input(self):
        """
        Select CD input
        """
        return self.input_select('07')

    def select_rec2_input(self):
        """
        Select Rec 2 Input
        """
        return self.input_select('08')

    def select_direct_input(self):
        """
        Select Direct Input
        """
        return self.input_select('10')

    def input_select_previous(self):
        """
        Selects the previous input
        """
        return self._cmd('2', '02')

    def input_select_next(self):
        """
        Selects the next input
        """
        return self._cmd('2', '03')

    def set_audio_source_for_input(self, value):
        """
        Sets the audio source for the current input to analogue ('00'),
        digital ('01'), or HDMI ('02').
        """
        # Do we know what the current input actually is?
        if self.__active_input is None:
            self.input_select_next()
            self.input_select_previous()

        # Sanity checks
        if self.__active_input not in self.__audio_source_for_input.keys():
            raise TypeError("Cannot set audio source for input '%s'" \
                            % self.__active_input)
        if isinstance(value, (int, long)):
            value = '0%s' % value
        if value not in ['00', '01', '02']:
            raise ValueError("Audio source must be '00', '01', or '02'")

        return self._cmd('2', '04', value)

    def set_video_source_for_input(self, value):
        """
        Sets the video source for the current input to S-Video ('00'),
        component ('01'), composite ('02'), or HDMI ('03').
        """
        # Do we know what the current input actually is?
        if self.__active_input is None:
            self.input_select_next()
            self.input_select_previous()

        # Sanity checks
        if self.__active_input not in self.__video_source_for_input.keys():
            raise TypeError("Cannot set video source for input '%s'" \
                            % self.__active_input)
        if isinstance(value, (int, long)):
            value = '0%s' % value
        if value not in ['00', '01', '02', '03']:
            raise ValueError("Video source must be '00', '01', '02', or '03'")

        return self._cmd('2', '05', value)

    # Group 3: Tuner Commands ------------------------------------------------

    # TODO

    # Group 4: Audio Processing Commands -------------------------------------

    def set_stereo_mode_no_subwoofer(self):
        """
        Disables subwoofer in stereo listening mode. Returns true.
        """
        result = self._cmd('4', '01', '00')
        return False

    def set_stereo_mode_use_subwoofer(self):
        """
        Enables subwoofer in stereo listening mode. Returns false.
        """
        result = self._cmd('4', '01', '01')
        return True

    def next_digital_processing_mode(self):
        """
        Cycles through available DSP modes; the mode in use is returned as a
        string in the third posiotion of the tuple (the same as appears on the
        device display, e.g. PLII/Neo/DSP/etc.)
        """
        return self._cmd('4', '02')[2].strip()

    def next_codec(self):
        """
        Cycles through the available CODEC (e.g. DD/DTS), returning the value
        in use as a string in the third position of the tuple.
        """
        return self._cmd('4', '03')[2].strip()

    def get_digital_processing_mode(self):
        """
        Returns the currently active DSP mode. This queries the device and
        does not depend on the internal register.
        """
        return self._cmd('4', '04')[2].strip()

    def get_codec(self):
        """
        Like get_digital_processing_mode, but for the currently active CODEC.
        """
        return self._cmd('4', '05')[2].strip()

    # Group 5: Version Commands ----------------------------------------------

    def get_main_software_version(self):
        """
        Returns the software version in use on the amplifier.
        """
        return self._cmd('5', '01')[2]

    def get_protocol_version(self):
        """
        Returns the version of the protocol used to communicate with the
        amplifier.
        """
        return self._cmd('5', '02')[2]

    @property
    def power(self): return self.__power_state

    @property
    def volume(self): return self.__volume

    @property
    def bass(self): return self.__bass

    @property
    def treble(self): return self.__treble

    @property
    def subwoofer(self): return self.__subwoofer

    @property
    def lfe_trim(self): return self.__lfe_trim

    @property
    def mute(self): return self.__mute_state

    @property
    def dynamic_range(self): return self.__dynamic_range

    @property
    def osd(self): return self.__osd_on

    @property
    def lip_sync_delay(self): return self.__lip_sync

    @property
    def active_input(self):
        source_id = self.__active_input
        source_name = self.input_names.get(source_id)
        return source_id, source_name

    @property
    def audio_source_for_input(self):
        source_id = self.__audio_source_for_input.get(self.__active_input)
        source_name = self.audio_input_source.get(source_id)
        return source_id, source_name

    @property
    def video_source_for_input(self):
        source_id = self.__video_source_for_input.get(self.__active_input)
        source_name = self.video_input_source.get(source_id)
        return source_id, source_name

    @property
    def stereo_audio_mode(self):
        mode_id = self.__stereo_audio_mode
        mode_name = self.stereo_audio_modes.get(mode_id)
        return mode_id, mode_name

    @property
    def signal_processing_mode(self):
        return self.get_digital_processing_mode()

    @property
    def signal_codec(self):
        return self.get_codec()

    @property
    def main_software_version(self):
        return self.get_main_software_version()

    @property
    def protocol_version(self):
        return self.get_protocol_version()


