# 4,222 Introduction to Programming

![](assets/img/banner_course.png)

## Welcome

Welcome to the course "4,222 Introduction to Programming"! This repository contains all course materials, exercises, and administrative information you'll need throughout the semester.

Website: https://asallin.github.io/BEcon_4222_Introduction_Programming/

## Course Philosophy

The course aims to teach and coach young economists to code and work in a collaborative, structured and impactful way. The focus is on both traditional teaching and practical work, with guided exercises and project coaching in settings that reflect real work in research and industry.

## Course Goals

By the end of this course, students will be able to:

1. **Understand programming fundamentals and develop intermediate programming skills**: Grasp core programming concepts including variables, data types, control structures, and functions. Know how to write modular code, document functions and implement error handling, use object oriented programming.

2. **Write Clean and Efficient Code**: Develop the ability to write well-structured, readable, and maintainable code following best practices. Apply collaborative, reproducible code development practices.

3. **Design and execute projects in Economics and Econometrics in a collaborative, systematic and reproducible way.**: Apply computational thinking to break down complex problems into manageable components and implement solutions. Gain proficiency in using version control systems to manage code and collaborate with others. Know how to design relational database schemas and interact with relational data from Python. Understand central concepts of DevOps, including continuous integration workflows and automated testing.

## Prerequisites
This course builds on the materials covered in the course "Data Handling".

## Repository Structure

- `admin/` - Administrative materials and course information
- `course_materials/` - Weekly lecture materials and resources
- `exercise_sessions/` - Exercise and study session content
- `examination/` - Exam-related materials and guidelines


## Notes on compiling the Quarto documents

In the course, we're using `uv` for virtual environments. To render and preview Quarto documents and slides from the virtual environment, follow the following steps:

### Render and preview

Quarto needs to know which Python interpreter to use. Set `QUARTO_PYTHON` to the project's virtual environment, then render (to produce the html output) or preview (to preview your output).

Run these commands from the **project root** in your terminal, replacing `your-notebook.qmd` with the actual path and actual filename of your notebook.

**Windows — Command Prompt**:

(You might need to activate the venv with `.venv\Scripts\activate` at your root).

```bat
set QUARTO_PYTHON=.venv\Scripts\python.exe
quarto render path\your-notebook.qmd
quarto preview path\your-notebook.qmd
```

**Windows — PowerShell**:

```powershell
$env:QUARTO_PYTHON = ".venv\Scripts\python.exe"
quarto render path\your-notebook.qmd
quarto preview path\your-notebook.qmd
```

**macOS / Linux**:

```bash
export QUARTO_PYTHON=.venv/bin/python
quarto render path/your-notebook.qmd
quarto preview path/your-notebook.qmd
```

To stop the preview, press `Ctrl+C` in the terminal.

#### Previewing inside VS Code

If you use VS Code, install the [Quarto extension](https://marketplace.visualstudio.com/items?itemName=quarto.quarto). It adds a **Preview** button in the top-right toolbar (`Ctrl+Shift+K`) that renders and displays the output in a side panel, updating on every save.

> **Important:** The Preview button does **not** automatically use the uv virtual environment. You must set `QUARTO_PYTHON` before launching VS Code for the button to work. Run this once in your terminal **before** opening VS Code, replacing the path with your project's root:
>
> *Windows (Command Prompt):*
> ```bat
> set QUARTO_PYTHON=C:\path\to\your\project\.venv\Scripts\python.exe
> code .
> ```
> *macOS / Linux:*
> ```bash
> export QUARTO_PYTHON=/path/to/your/project/.venv/bin/python
> code .
> ```
>
> Alternatively, use the terminal commands above. They always work regardless of how VS Code was launched.
