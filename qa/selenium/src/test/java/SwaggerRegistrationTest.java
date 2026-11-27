import org.openqa.selenium.By;
import org.openqa.selenium.JavascriptExecutor;
import org.openqa.selenium.OutputType;
import org.openqa.selenium.TakesScreenshot;
import org.openqa.selenium.WebDriver;
import org.openqa.selenium.WebElement;
import org.openqa.selenium.chrome.ChromeDriver;
import org.openqa.selenium.support.ui.WebDriverWait;

import org.testng.Assert;
import org.testng.ITestResult;
import org.testng.Reporter;
import org.testng.annotations.AfterMethod;
import org.testng.annotations.BeforeMethod;
import org.testng.annotations.DataProvider;
import org.testng.annotations.Test;

import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.time.Duration;
import java.time.LocalDateTime;
import java.time.format.DateTimeFormatter;
import java.util.List;
import java.util.UUID;


public class SwaggerRegistrationTest {

    private WebDriver driver;
    private WebDriverWait wait;

    private String actualStatus;
    private String actualBody;

    private static final String RUN_ID =
            LocalDateTime.now().format(
                    DateTimeFormatter.ofPattern("yyyyMMdd_HHmmss")
            )
                    + "_"
                    + UUID.randomUUID().toString().substring(0, 8);

    private static final Path EVIDENCE_ROOT = Path.of(
            "target",
            "test-evidence",
            RUN_ID
    );

    @BeforeMethod
    public void openSwagger() {
        driver = null;
        actualStatus = null;
        actualBody = null;

        driver = new ChromeDriver();
        driver.manage().window().maximize();

        wait = new WebDriverWait(
                driver,
                Duration.ofSeconds(25)
        );

        driver.get(
                System.getProperty(
                        "swagger.url",
                        "http://127.0.0.1:8001/docs"
                )
        );

        wait.until(d ->
                !d.findElements(
                        By.cssSelector(".opblock")
                ).isEmpty()
        );
    }

    private WebElement registrationOperation() {
        return wait.until(d -> {
            List<WebElement> operations = d.findElements(
                    By.cssSelector(".opblock")
            );

            for (WebElement operation : operations) {
                List<WebElement> methods = operation.findElements(
                        By.cssSelector(".opblock-summary-method")
                );

                List<WebElement> paths = operation.findElements(
                        By.cssSelector(".opblock-summary-path")
                );

                if (methods.isEmpty() || paths.isEmpty()) {
                    continue;
                }

                String method = methods.get(0).getText().trim();
                String path = paths.get(0).getText().trim();

                if (method.equals("POST")
                        && path.equals("/api/v1/auth/register")) {
                    return operation;
                }
            }

            return null;
        });
    }

    private WebElement visibleElement(String selector) {
        return wait.until(d -> {
            List<WebElement> elements = registrationOperation()
                    .findElements(By.cssSelector(selector));

            for (WebElement element : elements) {
                if (element.isDisplayed() && element.isEnabled()) {
                    return element;
                }
            }

            return null;
        });
    }

    private void scrollTo(WebElement element) {
        ((JavascriptExecutor) driver).executeScript(
                "arguments[0].scrollIntoView({block: 'center'});",
                element
        );
    }

    private void submitRegistration(String json) {
        WebElement operation = registrationOperation();

        if (!operation.getAttribute("class").contains("is-open")) {
            WebElement summary = operation.findElement(
                    By.cssSelector(".opblock-summary")
            );

            scrollTo(summary);
            summary.click();
        }

        WebElement tryButton = visibleElement(".try-out__btn");
        scrollTo(tryButton);
        tryButton.click();

        WebElement bodyInput = visibleElement(
                "textarea.body-param__text"
        );

        scrollTo(bodyInput);
        bodyInput.clear();
        bodyInput.sendKeys(json);

        WebElement executeButton = visibleElement("button.execute");
        scrollTo(executeButton);
        executeButton.click();

        actualStatus = wait.until(d -> {
            List<WebElement> statuses = registrationOperation()
                    .findElements(
                            By.cssSelector(
                                    ".live-responses-table "
                                            + ".response-col_status"
                            )
                    );

            for (WebElement status : statuses) {
                String text = status.getText().trim();

                if (text.matches("(?s)^\\d{3}.*")) {
                    return text.substring(0, 3);
                }
            }

            return null;
        });

        actualBody = wait.until(d -> {
            List<WebElement> blocks = registrationOperation()
                    .findElements(
                            By.cssSelector(
                                    ".live-responses-table pre"
                            )
                    );

            for (WebElement block : blocks) {
                String text = block.getText().trim();

                if (!text.isEmpty()) {
                    return text;
                }
            }

            return null;
        });
    }

    @DataProvider(name = "invalidRegistrations")
    public Object[][] invalidRegistrations() {
        return new Object[][]{
                {
                        "Invalid email",
                        """
                        {
                          "first_name": "QA",
                          "last_name": "Applicant",
                          "email": "invalid-email",
                          "password": "QaTestPassword123!",
                          "account_type": "ngo"
                        }
                        """,
                        "email",
                        "value_error",
                        "QaTestPassword123!"
                },
                {
                        "Short password",
                        """
                        {
                          "first_name": "QA",
                          "last_name": "Applicant",
                          "email": "qa.selenium@example.com",
                          "password": "abc",
                          "account_type": "ngo"
                        }
                        """,
                        "password",
                        "string_too_short",
                        "abc"
                },
                {
                        "Missing last name",
                        """
                        {
                          "first_name": "QA",
                          "email": "qa.selenium@example.com",
                          "password": "QaTestPassword123!",
                          "account_type": "ngo"
                        }
                        """,
                        "last_name",
                        "missing",
                        "QaTestPassword123!"
                },
                {
                        "Volunteer signup",
                        """
                        {
                          "first_name": "QA",
                          "last_name": "Applicant",
                          "email": "qa.selenium@example.com",
                          "password": "QaTestPassword123!",
                          "account_type": "volunteer"
                        }
                        """,
                        "account_type",
                        "literal_error",
                        "QaTestPassword123!"
                },
                {
                        "Admin signup",
                        """
                        {
                          "first_name": "QA",
                          "last_name": "Applicant",
                          "email": "qa.selenium@example.com",
                          "password": "QaTestPassword123!",
                          "account_type": "admin"
                        }
                        """,
                        "account_type",
                        "literal_error",
                        "QaTestPassword123!"
                },
                {
                        "Client supplied admin role",
                        """
                        {
                          "first_name": "QA",
                          "last_name": "Applicant",
                          "email": "qa.selenium@example.com",
                          "password": "QaTestPassword123!",
                          "account_type": "ngo",
                          "role": "admin"
                        }
                        """,
                        "role",
                        "extra_forbidden",
                        "QaTestPassword123!"
                }
        };
    }

    @Test(dataProvider = "invalidRegistrations")
    public void rejectsInvalidRegistration(
            String scenario,
            String requestBody,
            String expectedField,
            String expectedFieldCode,
            String submittedPassword
    ) {
        submitRegistration(requestBody);

        Assert.assertEquals(
                actualStatus,
                "422",
                scenario + ": unexpected HTTP status"
        );

        String compact = actualBody.replaceAll("\\s+", "");

        Assert.assertTrue(
                compact.contains("\"error\":{"),
                scenario + ": missing error envelope"
        );

        Assert.assertTrue(
                compact.contains("\"code\":\"VALIDATION_ERROR\""),
                scenario + ": incorrect error code"
        );

        Assert.assertTrue(
                compact.contains("\"message\":"),
                scenario + ": missing error message"
        );

        Assert.assertTrue(
                compact.contains("\"fields\":["),
                scenario + ": missing field errors"
        );

        Assert.assertTrue(
                compact.contains(
                        "\"field\":\"" + expectedField + "\""
                ),
                scenario + ": expected field error not found"
        );

        Assert.assertTrue(
                compact.contains(
                        "\"code\":\"" + expectedFieldCode + "\""
                ),
                scenario + ": incorrect field error code"
        );

        Assert.assertFalse(
                actualBody.contains(submittedPassword),
                scenario + ": submitted password exposed"
        );

        Assert.assertFalse(
                compact.contains("\"input\":"),
                scenario + ": validation input exposed"
        );

        Assert.assertFalse(
                compact.contains("\"ctx\":"),
                scenario + ": validation context exposed"
        );

        Reporter.log("PASS: " + scenario, true);
    }

    @AfterMethod(alwaysRun = true)
    public void saveEvidenceAndCloseBrowser(ITestResult result) {
        String status;

        if (result.getStatus() == ITestResult.SUCCESS) {
            status = "PASS";
        } else if (result.getStatus() == ITestResult.FAILURE) {
            status = "FAIL";
        } else {
            status = "SKIP";
        }

        String scenario = result.getMethod().getMethodName();

        if (result.getParameters().length > 0) {
            scenario = String.valueOf(result.getParameters()[0]);
        }

        String safeName = scenario.replaceAll(
                "[^a-zA-Z0-9_-]",
                "_"
        );

        String timestamp = LocalDateTime.now().format(
                DateTimeFormatter.ofPattern(
                        "yyyyMMdd_HHmmss_SSS"
                )
        );

        Path evidenceDirectory = EVIDENCE_ROOT.resolve(status);
        String evidenceError = null;

        try {
            Files.createDirectories(evidenceDirectory);

            if (driver != null) {
                byte[] screenshotBytes;
                String screenshotType;

                try {
                    // Capture only the response table where possible.
                    WebElement responseTable = driver.findElement(
                            By.cssSelector(
                                    ".opblock.is-open "
                                            + ".live-responses-table"
                            )
                    );

                    scrollTo(responseTable);

                    screenshotBytes = responseTable.getScreenshotAs(
                            OutputType.BYTES
                    );

                    screenshotType = "response";

                } catch (Exception responseScreenshotError) {
                    // Fallback helps diagnose page/locator failures.
                    screenshotBytes = ((TakesScreenshot) driver)
                            .getScreenshotAs(OutputType.BYTES);

                    screenshotType = "browser";
                }

                Path screenshot = evidenceDirectory.resolve(
                        safeName
                                + "_"
                                + timestamp
                                + "_"
                                + screenshotType
                                + ".png"
                );

                Files.write(screenshot, screenshotBytes);

                Reporter.log(
                        "Screenshot: "
                                + screenshot.toAbsolutePath(),
                        true
                );
            }

            String summary =
                    "Run: " + RUN_ID + System.lineSeparator()
                            + "Scenario: " + scenario
                            + System.lineSeparator()
                            + "Status: " + status
                            + System.lineSeparator()
                            + "Time: " + LocalDateTime.now()
                            + System.lineSeparator()
                            + "Expected HTTP status: 422"
                            + System.lineSeparator()
                            + "Actual HTTP status: " + actualStatus
                            + System.lineSeparator()
                            + "Test: "
                            + result.getMethod().getMethodName()
                            + System.lineSeparator();

            if (result.getThrowable() != null) {
                summary +=
                        "Failure: "
                                + result.getThrowable().toString()
                                + System.lineSeparator();
            }

            Path summaryFile = evidenceDirectory.resolve(
                    safeName + "_" + timestamp + ".txt"
            );

            Files.writeString(
                    summaryFile,
                    summary,
                    StandardCharsets.UTF_8
            );

            if (actualBody != null) {
                Path responseFile = evidenceDirectory.resolve(
                        safeName
                                + "_"
                                + timestamp
                                + "_response.txt"
                );

                Files.writeString(
                        responseFile,
                        actualBody,
                        StandardCharsets.UTF_8
                );
            }

        } catch (Exception exception) {
            evidenceError = exception.toString();

            Reporter.log(
                    "EVIDENCE SAVE FAILED: " + evidenceError,
                    true
            );

        } finally {
            if (driver != null) {
                try {
                    driver.quit();
                } catch (Exception quitError) {
                    Reporter.log(
                            "Browser close failed: " + quitError,
                            true
                    );
                }

                driver = null;
            }
        }

        // Do not silently report complete evidence when saving failed.
        if (evidenceError != null) {
            throw new AssertionError(
                    "Could not save test evidence: " + evidenceError
            );
        }
    }
}