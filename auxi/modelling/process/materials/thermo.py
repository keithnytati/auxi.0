#!/usr/bin/env python3
"""
This module provides a material class that can do thermochemical calculations.
"""

import os
import sys
import copy

import numpy

from auxi.core.objects import Object, NamedObject
from auxi.tools.chemistry import stoichiometry as stoich
from auxi.tools.chemistry.stoichiometry import convert_compound as cc
from auxi.tools.chemistry import thermochemistry as thermo
from auxi.tools.materialphysicalproperties import coals

__version__ = '0.3.6'
__license__ = 'LGPL v3'
__copyright__ = 'Copyright 2016, Ex Mente Technologies (Pty) Ltd'
__author__ = 'Christoff Kok, Johan Zietsman'
__credits__ = ['Christoff Kok', 'Johan Zietsman']
__maintainer__ = 'Christoff Kok'
__email__ = 'christoff.kok@ex-mente.co.za'
__status__ = 'Planning'


class Material(NamedObject):
    """
    Represents a material consisting of multiple chemical compounds, having
    the ability to do thermochemical calculations.

    :param name: A name for the material.
    :param file_path: The location of the file containing the material's data.
    :param description: the material's description

    The format of the text file is as follows:

    * The items in a line are separated by one or more spaces or tabs.
    * The first line is a heading line. It contains the word "Compound" \
    followed by zero or more assay names.
    * Subsequent lines contain a compound formula and phase, followed by \
    a mass fraction for each assay.
    * The list of compounds and mass fractions can be ended off with a \
    "#" character. This indicates that custom material properties follow \
    below in the lines below the hash.
    * If a custom material property is defined, a value must be \
    provided for each assay name. A price custom property is used as an \
    example below.

    The following is an example of a material text file::

        Compound   IlmeniteA  IlmeniteB  IlmeniteC
        Al2O3[S1]  0.01160    0.01550    0.00941
        CaO[S]     0.00022    0.00001    0.00017
        Cr2O3[S]   0.00008    0.00022    0.00011
        Fe2O3[S1]  0.20200    0.47300    0.49674
        Fe3O4[S1]  0.00000    0.00000    0.00000
        FeO[S1]    0.27900    0.19100    0.00000
        K2O[S]     0.00004    0.00001    0.00005
        MgO[S]     0.01040    0.00580    0.01090
        MnO[S]     0.00540    0.00480    0.00525
        Na2O[S1]   0.00007    0.00005    0.00031
        P4O10[S]   0.00001    0.00032    0.00015
        SiO2[S1]   0.00850    0.00490    0.01744
        TiO2[S1]   0.47700    0.29400    0.45949
        V2O5[S]    0.00360    0.00800    0.00000
        #
        Price[USD/kg]  1.2        1.3        1.1

    If you are dealing with a carbonatious material, nou must add the:
    following custom properties:
    * IsCoal: Set it equal to 1 for a carbonaceous material, and to 0
      otherwise.
    * HHV[MJ/kg]: Set it equal to the higher heating value of the material with
      units of MJ/kg.
    """

    def __init__(self, name, file_path, description=None):
        # Initialise the material's properties.
        self.name = name
        """The material's name."""

        self.description = description
        """The material's description."""

        self.compounds = list()
        """The material's list of chemical compounds."""

        # Read the material's data from the file and prepare it for use.
        with open(file_path) as f:
            lines = f.readlines()
        lines = self._prepare_lines(lines)

        # Determine the assay names, and create a dictionary entry for each
        # assay.
        assay_names = lines[0].split(" ")
        del(assay_names[0:1])
        self.raw_assays = {}
        """A dictionary containing raw assays for this material."""
        self.converted_assays = {}
        """A dictionary containing converted assays for this material."""

        for assay_name in assay_names:
            self.raw_assays[assay_name] = numpy.array([])
            self.converted_assays[assay_name] = numpy.array([])

        # Read the compounds and assays.
        must_read_custom_properties = False
        for i in range(1, len(lines)):
            if lines[i].startswith("#"):
                must_read_custom_properties = True
                break
            strings = lines[i].split(" ")
            if len(strings) < len(assay_names) + 1:  # Not a full line.
                continue

            # Add the new compound.
            self.compounds.append(strings[0])

            # Add the mass fractions to the assays.
            for j in range(0, len(self.raw_assays)):
                assay_name = assay_names[j]
                self.raw_assays[assay_name] = numpy.append(
                    self.raw_assays[assay_name],
                    float(strings[j+1]))
                self.converted_assays[assay_name] = numpy.append(
                    self.converted_assays[assay_name],
                    float(strings[j+1]))

        # Read the custom properties.
        self.assay_custom_properties = dict()
        for j in range(0, len(self.raw_assays)):
            assay_name = assay_names[j]
            self.assay_custom_properties[assay_name] = dict()
        self.custom_properties = []
        if must_read_custom_properties:
            for i in range(i+1, len(lines)):
                strings = lines[i].split(" ")
                for j in range(0, len(self.raw_assays)):
                    assay_name = assay_names[j]
                    property_name = strings[0]
                    self.custom_properties.append(property_name)
                    property_dictionary = self.assay_custom_properties[
                        assay_name]
                    property_dictionary[property_name] = float(strings[j+1])

        # Initialise the remaining properties.
        self.compound_count = len(self.compounds)
        """The number of chemical compounds in the material."""

        self.elements = self._create_element_list()

    def __str__(self):
        if len(self.raw_assays) > 0:
            line_length = 20 + (3 + 14) * len(self.raw_assays) - 2
        else:
            line_length = 20 + len(self.name)
        result = "=" * line_length + "\n"
        result += "Material\n"
        result += "=" * line_length + "\n"
        result += "Name".ljust(20) + self.name + "\n"

        # Create the header line of the table.
        result += "-" * line_length + "\n"
        if len(self.raw_assays) > 0:
            result = result + "Composition Details (mass fractions)\n"
        result += "Compound".ljust(20)
        assay_names = sorted(self.raw_assays.keys())
        pad = ''
        for assay_name in assay_names:
            result += pad + assay_name[0:15].ljust(15)
            pad = '  '
        result += "\n"
        result += "-" * line_length + "\n"

        # Create the content lines of the table.
        for compound in sorted(self.compounds):
            result = result + compound.ljust(20)
            compound_index = self.get_compound_index(compound)
            pad = ''
            for assay_name in assay_names:
                result += pad + '{:.8e}'.format(
                    self.raw_assays[assay_name][compound_index]).rjust(15)
                pad = '  '
            result = result + "\n"

        # Write the total.
        result += "Total".ljust(20)
        pad = ''
        for assay_name in assay_names:
            total = 0.0
            for compound in sorted(self.compounds):
                compound_index = self.get_compound_index(compound)
                total += self.raw_assays[assay_name][compound_index]
            result += pad + '{:.8e}'.format(total).rjust(15)
            pad = '  '
        result = result + "\n"

        # Write the custom properties.
        if len(self.custom_properties) > 0:
            result += "-" * line_length + "\n"
            result += "Custom Properties:\n"
            result += "-" * line_length + "\n"
            first_assay = list(sorted(self.assay_custom_properties.keys()))[0]
            properties = list(sorted(
                self.assay_custom_properties[first_assay].keys()))
            for prop in properties:
                pad = ''
                result += prop.ljust(20)
                for assay_name in assay_names:
                    result += pad + "{:.8e}".format(
                        self.assay_custom_properties[assay_name][prop]
                        ).rjust(15)
                    pad = '  '
                result += "\n"
        result += "=" * line_length + "\n"

        return result

    def _prepare_lines(self, lines):
        """
        Prepare the lines read from the text file before starting to
        process it.

        :param lines: The lines to prepare.
        """

        result = list()

        for line in lines:
            # Remove all whitespace from the start and end of the line.
            line = line.strip()

            # Replace all tabs with spaces.
            line = line.replace("\t", " ")

            # Replace all repeating spaces with a single space.
            while line.find("  ") > -1:
                line = line.replace("  ", " ")

            result.append(line)

        return result

    def _create_element_list(self):
        """
        Extract an alphabetically sorted list of elements from the
        material's compounds.

        :returns: Alphabetically sorted list of elements.
        """

        element_set = stoich.elements(self.compounds)
        return sorted(list(element_set))

    def _isCoal(self, assay):
        if 'IsCoal' in self.custom_properties and \
           self.assay_custom_properties[assay].get('IsCoal', 0) == 1:
            return True
        return False

    def _get_HHV(self, assay):
        return self.assay_custom_properties[assay].get('HHV[MJ/kg]', None)

    def get_compound_index(self, compound):
        """
        Determine the specified compound's index.

        :param compound: Formula and phase of a compound, e.g. "Fe2O3[S1]".

        :returns: Compound index.
        """

        return self.compounds.index(compound)

    def create_empty_assay(self):
        """
        Create an empty array to store an assay.

        The array's length will be equal to the number of compounds in the
        material.

        :returns: Empty assay array.
        """

        return numpy.zeros(self.compound_count)

    def add_assay(self, name, assay):
        """
        Add an assay to the material.

        :param name:  Assay name.
        :param assay: Numpy array containing the compound mass fractions for
          the assay. The sequence of the assay's elements must correspond to
          the sequence of the material's compounds.
        """

        if not type(assay) is numpy.ndarray:
            raise Exception("Invalid assay. It must be a numpy array.")
        elif not assay.shape == (self.compound_count,):
            raise Exception("Invalid assay: It must have the same number of "
                            "elements as the material has compounds.")
        elif name in self.raw_assays.keys():
            raise Exception("Invalid assay: An assay with that name already "
                            "exists.")
        self.raw_assays[name] = assay
        self.converted_assays[name] = assay

    def get_assay_total(self, name):
        """
        Calculate the total/sum of the specified assay's mass fractions.

        :param name: Assay name.

        :returns: Total mass fraction.
        """

        return sum(self.converted_assays[name])

    def create_package(self, assay=None, mass=0.0, P=1.0, T=25.0,
                       normalise=True):
        """
        Create a MaterialPackage based on the specified parameters.

        :param assay:     Name of the assay to be used to create the package.
        :param mass:      Package mass. [kg]
        :param P:         Package pressure. [atm]
        :param T:         Package temperature. [°C]
        :param normalise: Indicates whether the assay must be normalised
          before creating the package.

        :returns: MaterialPackage object.
        """

        if assay is None:
            return MaterialPackage(self, self.create_empty_assay(), P, T)

        if normalise:
            assay_total = self.get_assay_total(assay)
        else:
            assay_total = 1.0

        return MaterialPackage(self, mass * self.converted_assays[assay] /
                               assay_total, P, T, self._isCoal(assay),
                               self._get_HHV(assay))

    def create_stream(self, assay=None, mfr=0.0, P=1.0, T=25.0,
                      normalise=True):
        """
        Create a MaterialStream based on the specified parameters.

        :param assay: Name of the assay to be used to create the stream.
        :param mfr: Stream mass flow rate. [kg/h]
        :param P: Stream pressure. [atm]
        :param T: Stream temperature. [°C]
        :param normalise: Indicates whether the assay must be normalised
        before creating the Stream.

        :returns: MaterialStream object.
        """

        if assay is None:
            return MaterialStream(self, self.create_empty_assay(), P, T)

        if normalise:
            assay_total = self.get_assay_total(assay)
        else:
            assay_total = 1.0

        return MaterialStream(self, mfr * self.converted_assays[assay] /
                              assay_total, P, T, self._isCoal(assay),
                              self._get_HHV(assay))


class MaterialPackage(Object):
    """
    Represents a quantity of material consisting of multiple chemical
    compounds, having a specific mass, pressure, temperature and enthalpy.

    :param material: a reference to the Material to which self belongs
    :param compound_masses: [kg] package compound masses
    :param P: [atm] package pressure
    :param T: [°C] package temperature
    :param isCoal: a boolean that indicates whether the material is coal
    :param HHV: [MJ/kg] higher heating value of the coal
    """

    def __init__(self, material, compound_masses, P=1.0, T=25.0, isCoal=False,
                 HHV=None):
        # Confirm that the parameters are OK.
        if not type(material) is Material:
            raise TypeError("Invalid material type. Must be "
                            "thermomaterial.Material")
        if not type(compound_masses) is numpy.ndarray:
            raise TypeError("Invalid compound_masses type. Must be "
                            "numpy.ndarray.")

        # Initialise the object's properties.
        self.material = material
        self._P = P
        self._T = T
        self.isCoal = isCoal
        self.HHV = HHV
        self._compound_masses = compound_masses
        if self.mass > 0.0:
            if self.isCoal:
                self._DH298 = self._calculate_DH298_coal()
            self._H = self._calculate_H(T)
        else:
            self._H = 0.0

        self.custom_properties = dict()

    def __str__(self):
        b1 = '='*67 + '\n'
        b2 = '-'*67 + '\n'
        result = b1
        result += "MaterialPackage\n"
        result += b1
        result += "Material".ljust(20) + self.material.name + "\n"
        result += "Mass".ljust(20) + '{:.8e}'.format(
            self.mass).rjust(15) + " kg\n"
        result += "Amount".ljust(20) + '{:.8e}'.format(
            self.amount).rjust(15) + " kmol\n"
        result += "Pressure".ljust(20) + '{:.8e}'.format(
            self.P).rjust(15) + " atm\n"
        result += "Temperature".ljust(20) + '{:.8e}'.format(
            self.T).rjust(15) + " °C\n"
        result += "Enthalpy".ljust(20) + '{:.8e}'.format(
            self.H).rjust(15) + " kWh\n"
        result += b2
        result += "Compound Details\n"
        result += "Formula".ljust(20) + "Mass".ljust(16) + \
                  "Mass Fraction".ljust(16) + \
                  "Mole Fraction".ljust(16) + "\n"
        result += b2
        mass = self.mass
        compound_moles = self.get_compound_amounts()
        total_moles = compound_moles.sum()
        if mass > 0.0:
            for compound in self.material.compounds:
                index = self.material.get_compound_index(compound)
                result += compound.ljust(20) + '{:.8e}'.format(
                    self._compound_masses[index])
                result += "  " + \
                          '{:.8e}'.format(self._compound_masses[index] / mass)
                result += "  " + \
                          '{:.8e}'.format(compound_moles[index] / total_moles)
                result += "\n"
        else:
            for compound in self.material.compounds:
                index = self.material.get_compound_index(compound)
                result += compound.ljust(20) + '{:.8e}'.format(0.0)
                result += "  " + '{:.8e}'.format(0.0)
                result += "  " + '{:.8e}'.format(0.0)
                result += "\n"

        # Write the custom properties.
        if len(self.custom_properties) > 0:
            result += b2
            result += "Custom Properties:\n"
            result += b2
            properties = list(sorted(self.custom_properties.keys()))
            for prop in properties:
                result += prop.ljust(20)
                result += "{:.8e}".format(self.custom_properties[prop])
                result += "\n"

        result += b1
        return result

    def __add__(self, other):
        """
        Addition operator (+).

        Add this package (self) and 'other' together, return the result as a
        new package, and leave self unchanged.

        :param other: Can can be one of the following:
                 1. MaterialPackage
                    'other' is added to self to create a new package.
                 2. tuple: (compound, mass)
                    The specified mass of the specified compound is added to \
                    self, assuming the added material has the same \
                    temperature as self.
                 3. tuple: (compound, mass, temperature)
                    The specified mass of the specified compound at the \
                    specified temperature is added to self.

        :returns: A new Material package that is the sum of self and 'other'.
        """

        # Add another package.
        if type(other) is MaterialPackage:
            if self.material == other.material:  # Packages of same material.
                result = MaterialPackage(self.material,
                                         self._compound_masses +
                                         other._compound_masses)
                result.H = self._H + other._H
                result.P = self.P
                return result
            else:  # Packages of different materials.
                H = self.H + other.H
                result = self.clone()
                for compound in other.material.compounds:
                    if compound not in self.material.compounds:
                        raise Exception("Packages of '" + other.material.name +
                                        "' cannot be added to packages of '" +
                                        self.material.name +
                                        "'. The compound '" + compound +
                                        "' was not found in '" +
                                        self.material.name + "'.")
                    result = result + (compound,
                                       other.get_compound_mass(compound))
                result.H = H
                return result

        # Add the specified mass of the specified compound.
        elif self._is_compound_mass_tuple(other):
            # Added material varialbes.
            compound = other[0]
            index = self.material.get_compound_index(compound)
            mass = other[1]
            enthalpy = thermo.H(compound, self._T, mass)

            # Create the result package.
            result = self.clone()
            result._compound_masses[index] = result._compound_masses[index] + \
                mass
            result._H += enthalpy
            result._P = self._P
            return result

        # Add the specified mass of 'compound' at the specified temperature.
        elif self._is_compound_mass_temperature_tuple(other):
            # Added material varialbes.
            compound = other[0]
            index = self.material.get_compound_index(compound)
            mass = other[1]
            temperature = other[2]
            enthalpy = thermo.H(compound, temperature, mass)

            # Create the result package.
            result = self * 1.0
            result._compound_masses[index] = result._compound_masses[index] + \
                mass
            result.H = self._H + enthalpy
            result._P = self._P
            return result

        # If not one of the above, it must be an invalid argument.
        else:
            raise TypeError("Invalid addition argument.")

    def __mul__(self, scalar):
        """
        The multiplication operator (*).

        Create a new package by multiplying self with scalar.

        :param scalar: The result is a new package with its content equal to
          self multiplied by a scalar, leaving self unchanged.

        :returns: New MaterialPackage object.
        """

        # Multiply with a scalar floating point number.
        if type(scalar) is float or type(scalar) is numpy.float64 or \
           type(scalar) is numpy.float32:
            if scalar < 0.0:
                raise Exception("Invalid multiplication operation. Cannot "
                                "multiply package with negative number.")
            result = MaterialPackage(self.material, self._compound_masses *
                                     scalar, self._P, self._T)
            return result

        # If not one of the above, it must be an invalid argument.
        else:
            raise TypeError("Invalid multiplication argument.")

    def _calculate_H(self, T):
        """
        Calculate the enthalpy of the package at the specified temperature.

        :param T: Temperature. [°C]

        :returns: Enthalpy. [kWh]
        """

        if self.isCoal:
            return self._calculate_Hfr_coal(T)

        H = 0.0
        for compound in self.material.compounds:
            index = self.material.get_compound_index(compound)
            dH = thermo.H(compound, T, self._compound_masses[index])
            H = H + dH
        return H

    def _calculate_DH298_coal(self):
        """
        Calculate the enthalpy of formation of the package at the specified temperature, in
        case the material is coal.

        :returns: [kWh/kg] enthalpy of formation of daf coal
        """

        m_C = 0  # kg
        m_H = 0  # kg
        m_O = 0  # kg
        m_N = 0  # kg
        m_S = 0  # kg

        T = 25  # °C
        Hin = 0.0  # kWh
        for compound in self.material.compounds:
            index = self.material.get_compound_index(compound)
            if stoich.element_mass_fraction(compound, 'C') == 1.0:
                m_C += self._compound_masses[index]
                Hin = thermo.H(compound, T, self._compound_masses[index])
            elif stoich.element_mass_fraction(compound, 'H') == 1.0:
                m_H += self._compound_masses[index]
                Hin = thermo.H(compound, T, self._compound_masses[index])
            elif stoich.element_mass_fraction(compound, 'O') == 1.0:
                m_O += self._compound_masses[index]
                Hin = thermo.H(compound, T, self._compound_masses[index])
            elif stoich.element_mass_fraction(compound, 'N') == 1.0:
                m_N += self._compound_masses[index]
                Hin = thermo.H(compound, T, self._compound_masses[index])
            elif stoich.element_mass_fraction(compound, 'S') == 1.0:
                m_S += self._compound_masses[index]
                Hin = thermo.H(compound, T, self._compound_masses[index])

        m_total = m_C + m_H + m_O + m_N + m_S  # kg

        Hout = 0.0  # kWh
        Hout += thermo.H('CO2[G]', T, cc(m_C, 'C', 'CO2', 'C'))
        Hout += thermo.H('H2O[L]', T, cc(m_H, 'H', 'H2O', 'H'))
        Hout += thermo.H('O2[G]', T, m_O)
        Hout += thermo.H('N2[G]', T, m_N)
        Hout += thermo.H('SO2[G]', T, cc(m_S, 'S', 'SO2', 'S'))

        if self.HHV is None:
            # If no HHV is specified, calculate it from the proximate assay
            # using C-H-O-N-S.
            HHV = Hout - Hin / m_total  # kWh/kg
        else:
            # If an HHV is specified, convert it from MJ/kg to kWh/kg.
            HHV = self.HHV / 3.6  # kWh/kg

        return HHV + Hout / m_total  # kWh/kg

    def _calculate_H_coal(self, T):
        """
        Calculate the enthalpy of the package at the specified temperature, in
        case the material is coal.

        :param T: [°C] temperature

        :returns: [kWh] enthalpy
        """

        m_C = 0  # kg
        m_H = 0  # kg
        m_O = 0  # kg
        m_N = 0  # kg
        m_S = 0  # kg

        H = 0.0  # kWh/h
        for compound in self.material.compounds:
            index = self.material.get_compound_index(compound)
            if stoich.element_mass_fraction(compound, 'C') == 1.0:
                m_C += self._compound_masses[index]
            elif stoich.element_mass_fraction(compound, 'H') == 1.0:
                m_H += self._compound_masses[index]
            elif stoich.element_mass_fraction(compound, 'O') == 1.0:
                m_O += self._compound_masses[index]
            elif stoich.element_mass_fraction(compound, 'N') == 1.0:
                m_N += self._compound_masses[index]
            elif stoich.element_mass_fraction(compound, 'S') == 1.0:
                m_S += self._compound_masses[index]
            else:
                dH = thermo.H(compound, T, self._compound_masses[index])
                H += dH

        m_total = y_C + y_H + y_O + y_N + y_S  # kg/h
        y_C = m_C / m_total
        y_H = m_H / m_total
        y_O = m_O / m_total
        y_N = m_N / m_total
        y_S = m_S / m_total

        hmodel = coals.DafHTy()
        H = hmodel.calculate(T=T+273.15, y_C=y_C, y_H=y_H, y_O=y_O, y_N=y_N,
                             y_S=y_S) / 3.6e6  # kWh/kg
        H298 = hmodel.calculate(T=298.15, y_C=y_C, y_H=y_H, y_O=y_O, y_N=y_N,
                                y_S=y_S) / 3.6e6  # kWh/kg
        Hdaf = H - H298 + self._DH298  # kWh/kg
        Hdaf *= m_total  # kWh

        H += Hdaf

        return H

    def _calculate_T(self, H):
        """
        Calculate the temperature of the package given the specified
        enthalpy using a secant algorithm.

        :param H: Enthalpy. [kWh]

        :returns: Temperature. [°C]
        """

        # Create the initial guesses for temperature.
        x = list()
        x.append(self._T)
        x.append(self._T + 10.0)

        # Evaluate the enthalpy for the initial guesses.
        y = list()
        y.append(self._calculate_H(x[0]) - H)
        y.append(self._calculate_H(x[1]) - H)

        # Solve for temperature.
        for i in range(2, 50):
            x.append(x[i-1] - y[i-1]*((x[i-1] - x[i-2])/(y[i-1] - y[i-2])))
            y.append(self._calculate_H(x[i]) - H)
            if abs(y[i-1]) < 1.0e-5:
                break

        return x[len(x) - 1]

    def _is_compound_mass_tuple(self, value):
        """
        Determines whether value is a tuple of the format
        (compound(str), mass(float)).

        :param value: The value to be tested.

        :returns: True or False
        """

        if not type(value) is tuple:
            return False
        elif not len(value) == 2:
            return False
        elif not type(value[0]) is str:
            return False
        elif not type(value[1]) is float and \
                not type(value[1]) is numpy.float64 and \
                not type(value[1]) is numpy.float32:
            return False
        else:
            return True

    def _is_compound_mass_temperature_tuple(self, value):
        """Determines whether value is a tuple of the format
        (compound(str), mass(float), temperature(float)).

        :param value: The value to be tested.

        :returns: True or False"""

        if not type(value) is tuple:
            return False
        elif not len(value) == 3:
            return False
        elif not type(value[0]) is str:
            return False
        elif not type(value[1]) is float and \
                not type(value[1]) is numpy.float64 and \
                not type(value[1]) is numpy.float32:
            return False
        elif not type(value[1]) is float and \
                not type(value[1]) is numpy.float64 and \
                not type(value[1]) is numpy.float32:
            return False
        else:
            return True

    @property
    def H(self):
        """
        Get the enthalpy of the package.

        :returns: Enthalpy. [kWh]
        """

        return self._H

    @H.setter
    def H(self, H):
        """
        Set the enthalpy of the package to the specified value, and
        recalculate it's temperature.

        :param H: The new enthalpy value. [kWh]
        """

        self._H = H
        self._T = self._calculate_T(H)

    @property
    def T(self):
        """
        Get the temperature of of the package.

        :returns: Temperature. [°C]
        """

        return self._T

    @T.setter
    def T(self, T):
        """
        Set the temperature of the package to the specified value, and
        recalculate it's enthalpy.

        :param T: Temperature. [°C]
        """

        self._T = T
        self._H = self._calculate_H(T)

    @property
    def P(self):
        """Determine the pressure of the package.

        :returns: Pressure. [atm]"""

        return self._P

    @P.setter
    def P(self, P):
        """Set the pressure of the package to the specified value.

        :param P: Pressure. [atm]"""

        self._P = P

    # -------------------------------------------------------------------------
    # Public methods.
    # -------------------------------------------------------------------------
    def clone(self):
        """Create a complete copy of the package.

        :returns: A new MaterialPackage object."""

        result = copy.copy(self)
        result._compound_masses = copy.deepcopy(self._compound_masses)
        return result

    def clear(self):
        """
        Set all the compound masses in the package to zero.
        Set the pressure to 1, the temperature to 25 and the enthalpy to zero.
        """

        self._compound_masses = self._compound_masses * 0.0
        self._P = 1.0
        self._T = 25.0
        self._H = 0.0

    def get_assay(self):
        """
        Determine the assay of the package.

        :returns: Array of mass fractions.
        """

        return self._compound_masses / self._compound_masses.sum()

    @property
    def mass(self):
        """
        Get the mass of the package.

        :returns: [kg]
        """

        return self._compound_masses.sum()

    def get_compound_mass(self, compound):
        """
        Determine the mass of the specified compound in the package.

        :param compound: Formula and phase of a compound, e.g. "Fe2O3[S1]".

        :returns: Mass. [kg]
        """

        if compound in self.material.compounds:
            return self._compound_masses[
                self.material.get_compound_index(compound)]
        else:
            return 0.0

    def get_compound_amounts(self):
        """
        Determine the mole amounts of all the compounds.

        :returns: List of amounts. [kmol]
        """

        result = self._compound_masses * 1.0
        for compound in self.material.compounds:
            index = self.material.get_compound_index(compound)
            result[index] = stoich.amount(compound, result[index])
        return result

    def get_compound_amount(self, compound):
        """
        Determine the mole amount of the specified compound.

        :returns: Amount. [kmol]
        """

        index = self.material.get_compound_index(compound)
        return stoich.amount(compound, self._compound_masses[index])

    @property
    def amount(self):
        """
        Determine the sum of mole amounts of all the compounds.

        :returns: Amount. [kmol]
        """

        return sum(self.get_compound_amount(c) for c in self.material.compounds)

    def get_element_masses(self, elements=None):
        """
        Determine the masses of elements in the package.

        :returns: Array of element masses. [kg]
        """

        if elements is None:
            elements = self.material.elements
        result = numpy.zeros(len(elements))

        for compound in self.material.compounds:
            result += self.get_compound_mass(compound) *\
                numpy.array(stoich.element_mass_fractions(compound, elements))
        return result

    def get_element_mass_dictionary(self):
        """
        Determine the masses of elements in the package and return as a
        dictionary.

        :returns: Dictionary of element symbols and masses. [kg]
        """

        element_symbols = self.material.elements
        element_masses = self.get_element_masses()

        return {s: m for s, m in zip(element_symbols, element_masses)}

    def get_element_mass(self, element):
        """
        Determine the mass of the specified elements in the package.

        :returns: Masses. [kg]
        """

        result = numpy.zeros(1)
        for compound in self.material.compounds:
            result += self.get_compound_mass(compound) *\
                numpy.array(stoich.element_mass_fractions(compound, [element]))
        return result[0]

    def extract(self, other):
        """
        Extract 'other' from this package, modifying this package and
        returning the extracted material as a new package.

        :param other: Can be one of the following:

          * float: A mass equal to other is extracted from self. Self is
            reduced by other and the extracted package is returned as
            a new package.
          * tuple (compound, mass): The other tuple specifies the mass
            of a compound to be extracted. It is extracted from self and
            the extracted mass is returned as a new package.
          * string: The 'other' string specifies the compound to be
            extracted. All of the mass of that compound will be removed
            from self and a new package created with it.
          * Material: The 'other' material specifies the list of
            compounds to extract.


        :returns: New MaterialPackage object.
        """

        # Extract the specified mass.
        if type(other) is float or \
           type(other) is numpy.float64 or \
           type(other) is numpy.float32:
            return self._extract_mass(other)

        # Extract the specified mass of the specified compound.
        elif self._is_compound_mass_tuple(other):
            return self._extract_compound_mass(other[0], other[1])

        # Extract all of the specified compound.
        elif type(other) is str:
            return self._extract_compound(other)

        # TODO: Test
        # Extract all of the compounds of the specified material.
        elif type(other) is Material:
            return self._extract_material(other)

        # If not one of the above, it must be an invalid argument.
        else:
            raise TypeError("Invalid extraction argument.")

    def _extract_mass(self, mass):
        if mass > self.mass:
            raise Exception("Invalid extraction operation. \
                Cannot extract a mass larger than the package's mass.")
        fraction_to_subtract = mass / self.mass
        result = MaterialPackage(
            self.material, self._compound_masses *
            fraction_to_subtract, self._P, self._T)

        self._compound_masses = self._compound_masses * \
            (1.0 - fraction_to_subtract)
        self.T = self.T

        return result

    def _extract_compound(self, compound):
        result = self.material.create_package()

        if compound not in self.material.compounds:
            return result

        index = self.material.get_compound_index(compound)
        result._compound_masses[index] = self._compound_masses[index]
        result.T = self.T
        result.P = self.P

        self._compound_masses[index] = 0.0
        self.T = self.T

        return result

    def _extract_compound_mass(self, compound, mass):
        if compound not in self.material.compounds:
            return self.material.create_package()

        index = self.material.get_compound_index(compound)
        if mass > self._compound_masses[index]:
            raise Exception("Invalid extraction operation. Cannot extract a \
                compound mass larger than what the package contains.")
        self._compound_masses[index] = self._compound_masses[index] - mass
        self.T = self.T

        result = self.material.create_package(P=self._P, T=self._T)
        result += (compound, mass)

        return result

    def _extract_material(self, material):
        result = material.create_package()
        for compound in material.compounds:
            mass = self.get_compound_mass(compound)
            result += (compound, mass)
            self.extract(compound)
        result.T = self.T

        return result


class MaterialStream(Object):
    """
    Represents a flow of material consisting of multiple chemical compounds,
    having a specific mass flow rate, pressure, temperature and enthalpy.

    :param material: A reference to the Material to which the stream belongs.
    :param compound_mfrs: Compound mass flow rates. [kg/h]
    :param P: Stream pressure. [atm]
    :param T: Stream temperature. [°C]
    :param isCoal: a boolean that indicates whether the material is coal
    :param HHV: [MJ/kg] higher heating value of the coal
    """

    def __init__(self, material, compound_mfrs, P=1.0, T=25.0, isCoal=False,
                 HHV=None):
        # Confirm that the parameters are OK.
        if not type(material) is Material:
            raise TypeError("Invalid material type. Must be "
                            "thermomaterial.Material")
        if not type(compound_mfrs) is numpy.ndarray:
            raise TypeError("Invalid compound_mfrs type. Must be "
                            "numpy.ndarray.")

        # Initialise the object's properties.
        self.material = material
        self._P = P
        self._T = T
        self._compound_mfrs = compound_mfrs
        self.isCoal = isCoal
        self.HHV = HHV
        if self.mfr > 0.0:
            self._Hfr = self._calculate_Hfr(T)
        else:
            self._Hfr = 0.0

        self.custom_properties = dict()

    def __str__(self):
        b1 = '='*67 + '\n'
        b2 = '-'*67 + '\n'
        result = b1
        result += "MaterialStream\n"
        result += b1
        result += "Material".ljust(20) + self.material.name + "\n"
        result += "Mass Flow Rate".ljust(20) + '{:.8e}'.format(
            self.mfr).rjust(15) + " kg/h\n"
        result += "Amount Flow Rate".ljust(20) + '{:.8e}'.format(
            self.afr).rjust(15) + " kmol/h\n"
        result += "Pressure".ljust(20) + '{:.8e}'.format(
            self.P).rjust(15) + " atm\n"
        result += "Temperature".ljust(20) + '{:.8e}'.format(
            self.T).rjust(15) + " °C\n"
        result += "Enthalpy Flow Rate".ljust(20) + '{:.8e}'.format(
            self.Hfr).rjust(15) + " kWh/h\n"
        if self.isCoal:
            result += "HHV".ljust(20) + '{:.8e}'.format(self.HHV).rjust(15) + " MJ/kg\n"
        result += b2
        result += "Compound Details\n"
        result += "Formula".ljust(20) + "Mass".ljust(16) + \
                  "Mass Fraction".ljust(16) + \
                  "Mole Fraction".ljust(16) + "\n"
        result += b2
        mfr = self.mfr
        compound_afrs = self.get_compound_afrs()
        total_afr = compound_afrs.sum()
        if mfr > 0.0:
            for compound in self.material.compounds:
                index = self.material.get_compound_index(compound)
                result += compound.ljust(20) + '{:.8e}'.format(
                    self._compound_mfrs[index])
                result += "  " + \
                          '{:.8e}'.format(self._compound_mfrs[index] / mfr)
                result += "  " + \
                          '{:.8e}'.format(compound_afrs[index] / total_afr)
                result += "\n"
        else:
            for compound in self.material.compounds:
                index = self.material.get_compound_index(compound)
                result += compound.ljust(20) + '{:.8e}'.format(0.0)
                result += "  " + '{:.8e}'.format(0.0)
                result += "  " + '{:.8e}'.format(0.0)
                result += "\n"

        # Write the custom properties.
        if len(self.custom_properties) > 0:
            result += b2
            result += "Custom Properties:\n"
            result += b2
            properties = list(sorted(self.custom_properties.keys()))
            for prop in properties:
                result += prop.ljust(20)
                result += "{:.8e}".format(self.custom_properties[prop])
                result += "\n"

        result += b1
        return result

    def __add__(self, other):
        """
        Addition operator (+).

        Add this stream (self) and 'other' together, return the result as a
        new stream, and leave self unchanged.

        :param other: Can can be one of the following:
                 1. MaterialStream
                    'other' is added to self to create a new stream.
                 2. tuple: (compound, mass flow rate)
                    The specified mass flow rate of the specified compound is added to \
                    self, assuming the added material has the same \
                    temperature as self.
                 3. tuple: (compound, mass flow rate, temperature)
                    The specified mass flow rate of the specified compound at the \
                    specified temperature is added to self.

        :returns: A new MaterialStream that is the sum of self and 'other'.
        """

        # Add another stream.
        if type(other) is MaterialStream:
            if self.material == other.material:  # Streams of same material.
                if self.isCoal or other.isCoal:
                    HHV = 0
                    if self.HHV:
                        HHV += self.HHV * self.mfr
                    if other.HHV:
                        HHV += other.HHV * other.mfr
                    HHV /= self.mfr + other.mfr
                    isCoal = True
                else:
                    isCoal = False
                    HHV = None

                result = MaterialStream(self.material,
                                         self._compound_mfrs +
                                         other._compound_mfrs, isCoal=isCoal, HHV=HHV)
                result.Hfr = self._Hfr + other._Hfr
                result.P = self.P
                return result
            else:  # Streams of different materials.
                Hfr = self.Hfr + other.Hfr
                result = self.clone()
                for compound in other.material.compounds:
                    if compound not in self.material.compounds:
                        raise Exception("Streams of '" + other.material.name +
                                        "' cannot be added to streams of '" +
                                        self.material.name +
                                        "'. The compound '" + compound +
                                        "' was not found in '" +
                                        self.material.name + "'.")
                    result = result + (compound,
                                       other.get_compound_mfr(compound))
                result.Hfr = Hfr
                return result

        # Add the specified mass flow rate of the specified compound.
        elif self._is_compound_mfr_tuple(other):
            # Added material variables.
            compound = other[0]
            index = self.material.get_compound_index(compound)
            mfr = other[1]
            enthalpy = thermo.H(compound, self._T, mfr)

            # Create the result stream.
            result = self.clone()
            result._compound_mfrs[index] += mfr
            result._update_HHV(compound, mfr)
            result._Hfr += enthalpy
            result._P = self._P
            return result

        # Add the specified mass flow rate of 'compound' at the specified temperature.
        elif self._is_compound_mfr_temperature_tuple(other):
            # Added material varialbes.
            compound = other[0]
            index = self.material.get_compound_index(compound)
            mfr = other[1]
            temperature = other[2]
            enthalpy = thermo.H(compound, temperature, mfr)

            # Create the result stream.
            result = self * 1.0
            result._compound_mfrs[index] += mfr
            result.Hfr = self._Hfr + enthalpy
            result._P = self._P
            return result

        # If not one of the above, it must be an invalid argument.
        else:
            raise TypeError("Invalid addition argument.")

    def __mul__(self, scalar):
        """
        The multiplication operator (*).

        Create a new stream by multiplying self with scalar.

        :param scalar: The result is a new stream with its content equal to
          self multiplied by a scalar, leaving self unchanged.

        :returns: New MaterialStream object.
        """

        # Multiply with a scalar floating point number.
        if type(scalar) is float or type(scalar) is numpy.float64 or \
           type(scalar) is numpy.float32:
            if scalar < 0.0:
                raise Exception("Invalid multiplication operation. Cannot "
                                "multiply stream with negative number.")
            result = MaterialStream(self.material, self._compound_mfrs *
                                    scalar, self._P, self._T, self.isCoal,
                                    self.HHV)
            return result

        # If not one of the above, it must be an invalid argument.
        else:
            raise TypeError("Invalid multiplication argument.")

    def _calculate_Hfr(self, T):
        """
        Calculate the enthalpy flow rate of the stream at the specified
        temperature.

        :param T: Temperature. [°C]

        :returns: Enthalpy flow rate. [kWh/h]
        """

        if self.isCoal:
            return self._calculate_Hfr_coal(T)

        Hfr = 0.0
        for compound in self.material.compounds:
            index = self.material.get_compound_index(compound)
            dHfr = thermo.H(compound, T, self._compound_mfrs[index])
            Hfr = Hfr + dHfr
        return Hfr

    def _calculate_DH298_coal(self):
        """
        Calculate the enthalpy of formation of the dry-ash-free (daf) component of the coal.

        :returns: [kWh/kg daf] enthalpy of formation of daf coal
        """

        m_C = 0  # kg
        m_H = 0  # kg
        m_O = 0  # kg
        m_N = 0  # kg
        m_S = 0  # kg

        T = 25  # °C
        Hin = 0.0  # kWh
        for compound in self.material.compounds:
            index = self.material.get_compound_index(compound)
            formula = compound.split('[')[0]
            if stoich.element_mass_fraction(formula, 'C') == 1.0:
                m_C += self._compound_mfrs[index]
                Hin += thermo.H(compound, T, self._compound_mfrs[index])
            elif stoich.element_mass_fraction(formula, 'H') == 1.0:
                m_H += self._compound_mfrs[index]
                Hin += thermo.H(compound, T, self._compound_mfrs[index])
            elif stoich.element_mass_fraction(formula, 'O') == 1.0:
                m_O += self._compound_mfrs[index]
                Hin += thermo.H(compound, T, self._compound_mfrs[index])
            elif stoich.element_mass_fraction(formula, 'N') == 1.0:
                m_N += self._compound_mfrs[index]
                Hin += thermo.H(compound, T, self._compound_mfrs[index])
            elif stoich.element_mass_fraction(formula, 'S') == 1.0:
                m_S += self._compound_mfrs[index]
                Hin += thermo.H(compound, T, self._compound_mfrs[index])

        m_total = m_C + m_H + m_O + m_N + m_S  # kg

        Hout = 0.0  # kWh
        Hout += thermo.H('CO2[G]', T, cc(m_C, 'C', 'CO2', 'C'))
        Hout += thermo.H('H2O[L]', T, cc(m_H, 'H', 'H2O', 'H'))
        Hout += thermo.H('O2[G]', T, m_O)
        Hout += thermo.H('N2[G]', T, m_N)
        Hout += thermo.H('SO2[G]', T, cc(m_S, 'S', 'SO2', 'S'))
        Hout /= m_total

        if self.HHV is None:
            # If no HHV is specified, calculate it from the proximate assay
            # using C-H-O-N-S.
            HHV = (Hout - Hin) / m_total  # kWh/kg daf
        else:
            # If an HHV is specified, convert it from MJ/kg coal to kWh/kg daf.
            HHV = self.HHV / 3.6  # kWh/kg coal
            HHV *= self.mfr / m_total  # kWh/kg daf

        return HHV + Hout  # kWh/kg daf

    def _calculate_Hfr_coal(self, T):
        """
        Calculate the enthalpy flow rate of the stream at the specified
        temperature, in the case of it being coal.

        :param T: Temperature. [°C]

        :returns: Enthalpy flow rate. [kWh/h]
        """

        m_C = 0  # kg/h
        m_H = 0  # kg/h
        m_O = 0  # kg/h
        m_N = 0  # kg/h
        m_S = 0  # kg/h

        Hfr = 0.0  # kWh/h
        for compound in self.material.compounds:
            index = self.material.get_compound_index(compound)
            formula = compound.split('[')[0]
            if stoich.element_mass_fraction(formula, 'C') == 1.0:
                m_C += self._compound_mfrs[index]
            elif stoich.element_mass_fraction(formula, 'H') == 1.0:
                m_H += self._compound_mfrs[index]
            elif stoich.element_mass_fraction(formula, 'O') == 1.0:
                m_O += self._compound_mfrs[index]
            elif stoich.element_mass_fraction(formula, 'N') == 1.0:
                m_N += self._compound_mfrs[index]
            elif stoich.element_mass_fraction(formula, 'S') == 1.0:
                m_S += self._compound_mfrs[index]
            else:
                dHfr = thermo.H(compound, T, self._compound_mfrs[index])
                Hfr += dHfr

        m_total = m_C + m_H + m_O + m_N + m_S  # kg/h
        y_C = m_C / m_total
        y_H = m_H / m_total
        y_O = m_O / m_total
        y_N = m_N / m_total
        y_S = m_S / m_total

        hmodel = coals.DafHTy()
        H = hmodel.calculate(T=T+273.15, y_C=y_C, y_H=y_H, y_O=y_O, y_N=y_N,
                             y_S=y_S) / 3.6e6  # kWh/kg
        H298 = hmodel.calculate(T=298.15, y_C=y_C, y_H=y_H, y_O=y_O, y_N=y_N,
                                y_S=y_S) / 3.6e6  # kWh/kg
        Hdaf = H - H298 + self._DH298  # kWh/kg
        Hdaf *= m_total  # kWh/h

        Hfr += Hdaf

        return Hfr

    def _calculate_T(self, Hfr):
        """
        Calculate the temperature of the stream given the specified
        enthalpy flow rate using a secant algorithm.

        :param H: Enthalpy flow rate. [kWh/h]

        :returns: Temperature. [°C]
        """

        # Create the initial guesses for temperature.
        x = list()
        x.append(self._T)
        x.append(self._T + 10.0)

        # Evaluate the enthalpy for the initial guesses.
        y = list()
        y.append(self._calculate_Hfr(x[0]) - Hfr)
        y.append(self._calculate_Hfr(x[1]) - Hfr)

        # Solve for temperature.
        for i in range(2, 50):
            x.append(x[i-1] - y[i-1]*((x[i-1] - x[i-2])/(y[i-1] - y[i-2])))
            y.append(self._calculate_Hfr(x[i]) - Hfr)
            if abs(y[i-1]) < 1.0e-5:
                break

        return x[len(x) - 1]

    def _is_compound_mfr_tuple(self, value):
        """
        Determines whether value is a tuple of the format
        (compound(str), mfr(float)).

        :param value: The value to be tested.

        :returns: True or False
        """

        if not type(value) is tuple:
            return False
        elif not len(value) == 2:
            return False
        elif not type(value[0]) is str:
            return False
        elif not type(value[1]) is float and \
                not type(value[1]) is numpy.float64 and \
                not type(value[1]) is numpy.float32:
            return False
        else:
            return True

    def _is_compound_mfr_temperature_tuple(self, value):
        """Determines whether value is a tuple of the format
        (compound(str), mfr(float), temperature(float)).

        :param value: The value to be tested.

        :returns: True or False"""

        if not type(value) is tuple:
            return False
        elif not len(value) == 3:
            return False
        elif not type(value[0]) is str:
            return False
        elif not type(value[1]) is float and \
                not type(value[1]) is numpy.float64 and \
                not type(value[1]) is numpy.float32:
            return False
        elif not type(value[1]) is float and \
                not type(value[1]) is numpy.float64 and \
                not type(value[1]) is numpy.float32:
            return False
        else:
            return True

    @property
    def Hfr(self):
        """
        Get the enthalpy flow rate of the stream.

        :returns: Enthalpy flow rate. [kWh/h]
        """

        return self._Hfr

    @Hfr.setter
    def Hfr(self, Hfr):
        """
        Set the enthalpy flow rate of the stream to the specified value, and
        recalculate it's temperature.

        :param H: The new enthalpy flow rate value. [kWh/h]
        """

        self._Hfr = Hfr
        self._T = self._calculate_T(Hfr)

    @property
    def T(self):
        """
        Get the temperature of the stream.

        :returns: Temperature. [°C]
        """

        return self._T

    @T.setter
    def T(self, T):
        """
        Set the temperature of the stream to the specified value, and
        recalculate it's enthalpy.

        :param T: Temperature. [°C]
        """

        self._T = T
        self._Hfr = self._calculate_Hfr(T)

    @property
    def HHV(self):
        """
        Get the higher heating value of the stream.

        :returns: MJ/kg coal, higher heating value
        """

        return self._HHV

    @HHV.setter
    def HHV(self, HHV):
        """
        Set the higher heating value of the stream to the specified value, and
        recalculate the formation enthalpy of the daf coal.

        :param HHV: MJ/kg coal, higher heating value
        """

        self._HHV = HHV  # MJ/kg coal
        if self.isCoal:
            self._DH298 = self._calculate_DH298_coal()  # kWh/kg daf

    @property
    def P(self):
        """Determine the pressure of the stream.

        :returns: Pressure. [atm]"""

        return self._P

    @P.setter
    def P(self, P):
        """Set the pressure of the stream to the specified value.

        :param P: Pressure. [atm]"""

        self._P = P

    # -------------------------------------------------------------------------
    # Public methods.
    # -------------------------------------------------------------------------
    def clone(self):
        """Create a complete copy of the stream.

        :returns: A new MaterialStream object."""

        result = copy.copy(self)
        result._compound_mfrs = copy.deepcopy(self._compound_mfrs)
        return result

    def clear(self):
        """
        Set all the compound mass flow rates in the stream to zero.
        Set the pressure to 1, the temperature to 25 and the enthalpy to zero.
        """

        self._compound_mfrs = self._compound_mfrs * 0.0
        self._P = 1.0
        self._T = 25.0
        self._H = 0.0

    def get_assay(self):
        """
        Determine the assay of the stream.

        :returns: Array of mass fractions.
        """

        return self._compound_mfrs / self._compound_mfrs.sum()

    @property
    def mfr(self):
        """
        Get the mass flow rate of the stream.

        :returns: Mass flow rate. [kg/h]
        """

        return self._compound_mfrs.sum()

    def get_compound_mfr(self, compound):
        """
        Determine the mass flow rate of the specified compound in the stream.

        :param compound: Formula and phase of a compound, e.g. "Fe2O3[S1]".

        :returns: Mass flow rate. [kg/h]
        """

        if compound in self.material.compounds:
            return self._compound_mfrs[
                self.material.get_compound_index(compound)]
        else:
            return 0.0

    def get_compound_afrs(self):
        """
        Determine the amount flow rates of all the compounds.

        :returns: List of amount flow rates. [kmol/h]
        """

        result = self._compound_mfrs * 1.0
        for compound in self.material.compounds:
            index = self.material.get_compound_index(compound)
            result[index] = stoich.amount(compound, result[index])
        return result

    def get_compound_afr(self, compound):
        """
        Determine the amount flow rate of the specified compound.

        :returns: Amount flow rate. [kmol/h]
        """

        index = self.material.get_compound_index(compound)
        return stoich.amount(compound, self._compound_mfrs[index])

    @property
    def afr(self):
        """
        Determine the sum of amount flow rates of all the compounds.

        :returns: Amount flow rate. [kmol/h]
        """

        result = 0.0
        for compound in self.material.compounds:
            result += self.get_compound_afr(compound)
        return result

    def get_element_mfrs(self, elements=None):
        """
        Determine the mass flow rates of elements in the stream.

        :returns: Array of element mass flow rates. [kg/h]
        """

        if elements is None:
            elements = self.material.elements
        result = numpy.zeros(len(elements))
        for compound in self.material.compounds:
            result += self.get_compound_mfr(compound) *\
                stoich.element_mass_fractions(compound, elements)
        return result

    def get_element_mfr_dictionary(self):
        """
        Determine the mass flow rates of elements in the stream and return as
        a dictionary.

        :returns: Dictionary of element symbols and mass flow rates. [kg/h]
        """

        element_symbols = self.material.elements
        element_mfrs = self.get_element_mfrs()
        result = dict()
        for s, mfr in zip(element_symbols, element_mfrs):
            result[s] = mfr
        return result

    def get_element_mfr(self, element):
        """
        Determine the mass flow rate of the specified elements in the stream.

        :returns: Mass flow rates. [kg/h]
        """

        result = 0.0
        for compound in self.material.compounds:
            formula = compound.split('[')[0]
            result += self.get_compound_mfr(compound) *\
                stoich.element_mass_fraction(formula, element)
        return result

    def extract(self, other):
        """
        Extract 'other' from this stream, modifying this stream and returning
        the extracted material as a new stream.

        :param other: Can be one of the following:

          * float: A mass flow rate equal to other is extracted from self. Self
            is reduced by other and the extracted stream is returned as
            a new stream.
          * tuple (compound, mass): The other tuple specifies the mass flow
            rate of a compound to be extracted. It is extracted from self and
            the extracted mass flow rate is returned as a new stream.
          * string: The 'other' string specifies the compound to be
            extracted. All of the mass flow rate of that compound will be
            removed from self and a new stream created with it.
          * Material: The 'other' material specifies the list of
            compounds to extract.


        :returns: New MaterialStream object.
        """

        # Extract the specified mass flow rate.
        if type(other) is float or \
           type(other) is numpy.float64 or \
           type(other) is numpy.float32:
            return self._extract_mfr(other)

        # Extract the specified mass flow rateof the specified compound.
        elif self._is_compound_mfr_tuple(other):
            return self._extract_compound_mfr(other[0], other[1])

        # Extract all of the specified compound.
        elif type(other) is str:
            return self._extract_compound(other)

        # TODO: Test
        # Extract all of the compounds of the specified material.
        elif type(other) is Material:
            return self._extract_material(other)

        # If not one of the above, it must be an invalid argument.
        else:
            raise TypeError("Invalid extraction argument.")

    def _extract_mfr(self, mfr):
        if mfr > self.mfr:
            raise Exception("Invalid extraction operation. Cannot extract a "
                            "mass flow rate larger than the streams's mass "
                            "flow rate.")
        fraction_to_subtract = mfr / self.mfr
        result = MaterialStream(
            self.material, self._compound_mfrs *
            fraction_to_subtract, self._P, self._T)

        self._compound_mfrs = self._compound_mfrs * \
            (1.0 - fraction_to_subtract)
        self.T = self.T

        return result

    def _extract_compound(self, compound):
        result = self.material.create_stream()

        if compound not in self.material.compounds:
            return result

        index = self.material.get_compound_index(compound)
        mfr = self._compound_mfrs[index]

        result._compound_mfrs[index] = mfr
        result.T = self.T
        result.P = self.P

        self._compound_mfrs[index] = 0.0
        self._update_HHV(compound, -mfr)
        self.T = self.T

        return result

    def _update_HHV(self, compound, mfr):
        if self.isCoal:
            HHV = self.HHV * (self.mfr - mfr)  # MJ

            dH = thermo.H(compound, 25, mfr)  # kWh
            dH -= thermo.H('CO2[G]', 25, cc(mfr, compound, 'COs', 'C'))  # kWh
            dH -= thermo.H('H2O[L]', 25, cc(mfr, compound, 'H2O', 'H'))  # kWh
            dH -= thermo.H('SO2[G]', 25, cc(mfr, compound, 'SO2', 'S'))  # kWh
            dH *= 3.6  # MJ

            HHV += dH  # MJ
            HHV /= self.mfr  # MJ/kg coal

            self.HHV = HHV

    def _extract_compound_mfr(self, compound, mfr):
        if compound not in self.material.compounds:
            return self.material.create_stream()

        index = self.material.get_compound_index(compound)
        if mfr > self._compound_mfrs[index]:
            raise Exception("Invalid extraction operation. Cannot extract a "
                "compound mass flow rate larger than what the stream "
                "contains.")

        self._compound_mfrs[index] = self._compound_mfrs[index] - mfr
        self._update_HHV(compound, -mfr)
        self.T = self.T

        result = self.material.create_stream(P=self._P, T=self._T)
        result += (compound, mfr)

        return result

    def _extract_material(self, material):
        result = material.create_stream()
        for compound in material.compounds:
            mfr = self.get_compound_mfr(compound)
            result += (compound, mfr)
            self.extract(compound)
        result.T = self.T

        return result


def _get_default_data_path():
    module_path = os.path.dirname(sys.modules[__name__].__file__)
    data_path = os.path.join(module_path, r"../data")
    data_path = os.path.abspath(data_path)
    return data_path

DEFAULT_DATA_PATH = _get_default_data_path()
