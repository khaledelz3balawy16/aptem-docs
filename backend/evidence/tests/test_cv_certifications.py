from django.test import SimpleTestCase

from evidence.services.cv_certifications import (
    extract_certifications_and_education,
)


class CvCertificationExtractionTests(SimpleTestCase):
    def test_extracts_education_and_certifications(self):
        text = """
        Education
        BSc Information Systems and Management -University of London - 2014
        HND Business Administration - YABA College of Technology - 2004

        Certifications
        Professional Project Management - Google - 2024
        Advanced Excel and Power BI - Microsoft - 2022

        Interests
        Reading and travelling
        """

        results = extract_certifications_and_education(text)

        self.assertEqual(len(results), 4)
        self.assertEqual(results[0]["category"], "education")
        self.assertEqual(results[0]["issuer"], "University of London")
        self.assertEqual(results[0]["issued_date"], "2014")
        self.assertEqual(results[2]["category"], "certification")
        self.assertEqual(results[2]["issuer"], "Google")

    def test_combines_an_issuer_line_with_the_following_certificate(self):
        text = """
        Certificates
        The Chartered Institute of Marketing
        Chartered Diploma in Professional Marketing
        About Me
        Other content
        """

        results = extract_certifications_and_education(text)

        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["name"], "Chartered Diploma in Professional Marketing")
        self.assertEqual(results[0]["issuer"], "The Chartered Institute of Marketing")

    def test_does_not_extract_similar_words_outside_relevant_sections(self):
        text = """
        Professional Experience
        Delivered staff training and managed certification compliance.
        Interests
        Reading
        """

        self.assertEqual(extract_certifications_and_education(text), [])

    def test_recognizes_spaced_and_variant_section_headings(self):
        text = """
        E D U C A T I O N
        BSc Computer Science - University of Kent - 2020
        C O U R S E S
        PRINCE2 Foundation - PeopleCert - 2021
        S K I L L S
        Stakeholder management
        """

        results = extract_certifications_and_education(text)

        self.assertEqual(len(results), 2)
        self.assertEqual(results[0]["category"], "education")
        self.assertEqual(results[1]["category"], "certification")

    def test_lowercase_sentence_ending_in_courses_does_not_start_a_section(self):
        text = """
        Employment History
        Produced marketing materials for several training courses.
        Managed bookings and customer communications.
        Education and training
        BA Hons Design - Brunel University - 1998
        Computer literacy
        Word and Excel
        """

        results = extract_certifications_and_education(text)

        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["name"], "BA Hons Design")

    def test_extracts_letter_spaced_education_entries(self):
        text = """
        E D U C A T I O N
        B T E C L E V E L 4 D I P L O M A I N F O U N D A T I O N A R T
        T E N G C S E S A T G R A D E S A B
        S K I L L S
        P H O T O S H O P
        """

        results = extract_certifications_and_education(text)

        self.assertEqual(len(results), 2)
        self.assertTrue(all(row["category"] == "education" for row in results))

    def test_stops_before_skills_and_attributes(self):
        text = """
        Certifications
        PRINCE2 Foundation - PeopleCert - 2022
        Skills & Attributes
        Adaptability - able to respond to change
        """

        results = extract_certifications_and_education(text)

        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["name"], "PRINCE2 Foundation")

    def test_splits_semicolon_separated_certifications(self):
        text = """
        Certifications
        APM PMQ; APM PFQ; EUSR Water Hygiene
        Work Experience
        Project Manager
        """

        results = extract_certifications_and_education(text)

        self.assertEqual([row["name"] for row in results], [
            "APM PMQ",
            "APM PFQ",
            "EUSR Water Hygiene",
        ])
